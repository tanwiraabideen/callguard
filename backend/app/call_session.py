"""Tracks one browser's connection: its messages and the call audio it sends.

Audio arrives as binary frames of 16-bit stereo samples, left = caller and
right = user. Each chunk is counted and passed on to transcription.
"""

import json
import logging
import time
from collections.abc import Awaitable, Callable

from app.calls import load_generated_calls
from app.config import settings
from app.risk.engine import RiskEngine
from app.transcription import create_transcriber
from app.transcription.segments import TranscriptionError

logger = logging.getLogger("uvicorn.error")


def error(detail: str) -> dict:
    return {"type": "error", "detail": detail}


class CallSession:
    def __init__(self, send: Callable[[dict], Awaitable[None]]) -> None:
        self.send = send
        self.connected = True
        self.call_id: str | None = None
        self.transcriber = None
        self.risk_engine: RiskEngine | None = None
        self.bytes_received = 0
        self.next_progress_seconds = 0.0

    @property
    def seconds_received(self) -> float:
        return self.bytes_received / settings.audio_bytes_per_second

    async def handle_text(self, raw: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(error("Message must be valid JSON"))
            return

        if not isinstance(message, dict):
            await self.send(error("Message must be a JSON object"))
            return

        message_type = message.get("type")
        if message_type == "ping":
            # sent_at is echoed so the browser can measure the round trip.
            await self.send(
                {"type": "pong", "sent_at": message.get("sent_at"), "server_time": time.time()}
            )
        elif message_type == "call_start":
            await self.start_call(message.get("call_id"))
        elif message_type == "call_end":
            await self.end_call(message.get("reason", "unknown"))
        else:
            await self.send(error(f"Unknown message type: {message_type}"))

    async def start_call(self, call_id: object) -> None:
        calls = load_generated_calls()
        if not isinstance(call_id, str) or call_id not in calls:
            await self.send(error(f"Unknown call: {call_id}"))
            return

        await self.stop_transcriber()
        self.cancel_risk_engine()
        self.call_id = call_id
        self.risk_engine = RiskEngine(self.send_if_connected)
        self.bytes_received = 0
        self.next_progress_seconds = settings.audio_progress_interval_seconds
        logger.info("Call started: %s", call_id)
        await self.send(
            {
                "type": "call_started",
                "call_id": call_id,
                "transcription_mode": settings.active_transcription_mode,
                "llm_mode": settings.llm_model if settings.llm_active else "off (rules only)",
            }
        )

        self.transcriber = create_transcriber(calls[call_id], self.send_segment)
        try:
            await self.transcriber.start()
        except TranscriptionError as failure:
            await self.transcription_failed(failure)

    async def end_call(self, reason: object) -> None:
        if self.call_id is None:
            await self.send(error("No call in progress"))
            return

        # Finish first, so the last words and scores arrive before call_ended.
        await self.stop_transcriber()
        if self.risk_engine is not None:
            await self.risk_engine.finish()
            self.risk_engine = None

        reply = {
            "type": "call_ended",
            "call_id": self.call_id,
            "reason": reason,
            "seconds_received": round(self.seconds_received, 2),
            "bytes_received": self.bytes_received,
        }
        logger.info("Call ended: %s", reply)
        self.call_id = None
        await self.send(reply)

    async def handle_audio(self, chunk: bytes) -> None:
        if self.call_id is None:
            await self.send(error("Audio received with no call in progress"))
            return
        if len(chunk) % settings.audio_bytes_per_frame != 0:
            await self.send(error("Audio chunk is not a whole number of stereo frames"))
            return

        self.bytes_received += len(chunk)
        if self.transcriber is not None:
            try:
                await self.transcriber.send_audio(chunk)
            except TranscriptionError as failure:
                await self.transcription_failed(failure)

        if self.seconds_received >= self.next_progress_seconds:
            self.next_progress_seconds += settings.audio_progress_interval_seconds
            await self.send(
                {"type": "audio_progress", "seconds_received": round(self.seconds_received, 2)}
            )

    async def send_if_connected(self, message: dict) -> None:
        if self.connected:
            await self.send(message)

    async def send_segment(self, segment: dict) -> None:
        await self.send_if_connected({"type": "transcript", **segment})
        if self.risk_engine is not None:
            await self.risk_engine.add_segment(segment)

    async def transcription_failed(self, failure: TranscriptionError) -> None:
        # The call keeps playing, and there is deliberately no switch to mock,
        # so that a mock transcript can never be mistaken for a real one.
        logger.warning("Transcription failed: %s", failure)
        self.transcriber = None
        await self.send(error(str(failure)))

    async def stop_transcriber(self) -> None:
        if self.transcriber is not None:
            transcriber, self.transcriber = self.transcriber, None
            await transcriber.finish()

    def cancel_risk_engine(self) -> None:
        if self.risk_engine is not None:
            self.risk_engine.cancel()
            self.risk_engine = None

    async def close(self) -> None:
        """The browser has gone, so clean up without sending anything."""
        self.connected = False
        await self.stop_transcriber()
        self.cancel_risk_engine()
