"""Streams call audio to ElevenLabs Scribe and turns its results into segments.

Scribe takes one audio channel per connection, so each speaker gets their own
connection. That also means every result is tied to its speaker automatically.
"""

import asyncio
import base64
import json
import logging
from array import array
from urllib.parse import urlencode

import websockets

from app.config import settings
from app.transcription.segments import (
    OnSegment,
    TranscriptionError,
    make_interim_segment,
    make_segment,
)

logger = logging.getLogger("uvicorn.error")

ERROR_FIELD = "error"


def build_url() -> str:
    query = urlencode(
        {
            "model_id": settings.scribe_model,
            "language_code": settings.scribe_language,
            "audio_format": f"pcm_{settings.audio_sample_rate}",
            "commit_strategy": "vad",
            "vad_silence_threshold_secs": settings.scribe_vad_silence_seconds,
            "include_timestamps": "true",
        }
    )
    return f"{settings.scribe_url}?{query}"


def audio_message(samples: bytes, commit: bool = False) -> str:
    return json.dumps(
        {
            "message_type": "input_audio_chunk",
            "audio_base_64": base64.b64encode(samples).decode(),
            "commit": commit,
            "sample_rate": settings.audio_sample_rate,
        }
    )


class ElevenLabsTranscriber:
    def __init__(self, on_segment: OnSegment) -> None:
        self.on_segment = on_segment
        self.connections: dict[str, websockets.ClientConnection] = {}
        self.receivers: list[asyncio.Task] = []
        self.failure: str | None = None
        self.seconds_sent = 0.0
        self.interim_start: dict[str, float | None] = {"caller": None, "user": None}
        self.finishing = False
        self.speakers_flushed: set[str] = set()
        self.all_flushed = asyncio.Event()

    async def start(self) -> None:
        try:
            caller, user = await asyncio.gather(self.connect(), self.connect())
        except (OSError, TimeoutError, websockets.WebSocketException) as error:
            raise TranscriptionError(f"Could not connect to ElevenLabs: {error}") from error

        self.connections = {"caller": caller, "user": user}
        self.receivers = [
            asyncio.create_task(self.receive_results(speaker, connection))
            for speaker, connection in self.connections.items()
        ]

    async def connect(self) -> websockets.ClientConnection:
        return await websockets.connect(
            build_url(),
            additional_headers={"xi-api-key": settings.elevenlabs_api_key},
        )

    async def send_audio(self, chunk: bytes) -> None:
        if self.failure:
            raise TranscriptionError(self.failure)

        # The stereo chunk alternates caller and user samples.
        samples = array("h")
        samples.frombytes(chunk)
        channels = {"caller": samples[0::2], "user": samples[1::2]}
        self.seconds_sent += len(chunk) / settings.audio_bytes_per_second

        try:
            for speaker, connection in self.connections.items():
                await connection.send(audio_message(channels[speaker].tobytes()))
        except websockets.WebSocketException as error:
            raise TranscriptionError(f"Lost connection to ElevenLabs: {error}") from error

    async def receive_results(
        self, speaker: str, connection: websockets.ClientConnection
    ) -> None:
        try:
            async for raw in connection:
                await self.handle_result(speaker, json.loads(raw))
        except Exception as error:
            logger.warning("Stopped reading ElevenLabs results: %s", error)

    async def handle_result(self, speaker: str, result: dict) -> None:
        message_type = result.get("message_type")

        if ERROR_FIELD in result:
            self.failure = f"ElevenLabs {message_type}: {result[ERROR_FIELD]}"
            logger.warning(self.failure)

        elif message_type == "partial_transcript" and result["text"].strip():
            # Scribe gives no word times until a segment is committed, so an
            # interim segment is stamped with when its words first appeared.
            if self.interim_start[speaker] is None:
                self.interim_start[speaker] = self.seconds_sent
            await self.on_segment(
                make_interim_segment(speaker, result["text"], self.interim_start[speaker])
            )

        elif message_type == "committed_transcript_with_timestamps":
            self.interim_start[speaker] = None
            words = [
                {"word": word["text"], "start": word["start"], "end": word["end"]}
                for word in result.get("words") or []
                if word["type"] == "word"
            ]
            if words:
                await self.on_segment(make_segment(speaker, words, True))

            if self.finishing:
                self.speakers_flushed.add(speaker)
                if len(self.speakers_flushed) == len(self.connections):
                    self.all_flushed.set()

    async def finish(self) -> None:
        """Ask for each speaker's last words, then close both connections."""
        self.finishing = True
        try:
            for connection in self.connections.values():
                await connection.send(audio_message(b"", commit=True))
            await asyncio.wait_for(
                self.all_flushed.wait(), timeout=settings.scribe_close_timeout_seconds
            )
        except TimeoutError:
            logger.warning("Timed out waiting for the last ElevenLabs results")
        except websockets.WebSocketException as error:
            logger.warning("ElevenLabs closed early: %s", error)

        for receiver in self.receivers:
            receiver.cancel()
        for connection in self.connections.values():
            await connection.close()
