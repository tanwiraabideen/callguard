"""Tracks one browser's connection: its messages and the call audio it sends.

Audio arrives as binary frames of 16-bit stereo samples, left = caller and
right = user. Each chunk is counted and passed on to transcription, whose
sentences feed the risk engine, the alerts and the agent.
"""

import asyncio
import json
import logging
import time
from array import array
from collections.abc import Awaitable, Callable

from app.agent.controller import AgentController
from app.calls import load_generated_calls
from app.config import settings
from app.risk.alerts import AlertManager
from app.risk.engine import RiskEngine
from app.speech import speech_message
from app.summary import build_summary
from app.trace import trace_event
from app.transcription import create_transcriber
from app.transcription.segments import TranscriptionError

logger = logging.getLogger("uvicorn.error")

LIVE_CALL_ID = "live"


def error(detail: str) -> dict:
    return {"type": "error", "detail": detail}


class CallSession:
    def __init__(self, send: Callable[[dict], Awaitable[None]]) -> None:
        self.send = send
        self.connected = True
        self.call_id: str | None = None
        self.title = ""
        self.transcriber = None
        self.risk_engine: RiskEngine | None = None
        self.alerts = AlertManager()
        self.agent: AgentController | None = None
        self.speech_tasks: set[asyncio.Task] = set()
        self.limit_reached = False
        self.bytes_received = 0
        self.peak_levels = {"caller": 0, "user": 0}
        self.next_progress_seconds = 0.0
        self.peak_levels = {"caller": 0, "user": 0}

    @property
    def seconds_received(self) -> float:
        return self.bytes_received / settings.audio_bytes_per_second

    async def send_if_connected(self, message: dict) -> None:
        if self.connected:
            await self.send(message)

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
        elif message_type == "keepalive":
            pass  # any traffic stops the host from closing an idle connection
        elif message_type == "call_start":
            await self.start_call(message.get("call_id"))
        elif message_type == "call_end":
            await self.end_call(message.get("reason", "unknown"))
        elif message_type == "dismiss_alert":
            await self.dismiss_alert(message.get("alert_id"))
        else:
            await self.send(error(f"Unknown message type: {message_type}"))

    async def start_call(self, call_id: object) -> None:
        calls = load_generated_calls()
        is_live = call_id == LIVE_CALL_ID
        if is_live and settings.active_transcription_mode != "elevenlabs":
            await self.send(error("Live calls need ELEVENLABS_API_KEY in backend/.env"))
            return
        if not is_live and (not isinstance(call_id, str) or call_id not in calls):
            await self.send(error(f"Unknown call: {call_id}"))
            return

        await self.clean_up_call()
        call = None if is_live else calls[call_id]
        self.call_id = call_id
        self.title = "Live call" if is_live else call["title"]
        self.limit_reached = False
        self.bytes_received = 0
        self.peak_levels = {"caller": 0, "user": 0}
        self.next_progress_seconds = settings.audio_progress_interval_seconds
        self.alerts = AlertManager()
        self.risk_engine = RiskEngine(self.handle_risk_message)
        self.agent = AgentController(
            self.risk_engine, self.speak, self.agent_end_call, self.send_if_connected
        )
        logger.info("Call started: %s", call_id)
        await self.send(
            {
                "type": "call_started",
                "call_id": call_id,
                "transcription_mode": settings.active_transcription_mode,
                "llm_mode": settings.llm_model if settings.llm_active else "off (rules only)",
                "agent_mode": settings.agent_model if settings.agent_llm_active else "fixed policy",
                "max_seconds": settings.max_call_seconds,
                "medium_threshold": settings.risk_medium_threshold,
                "high_threshold": settings.risk_high_threshold,
            }
        )

        self.transcriber = create_transcriber(call, self.send_segment)
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
        await self.risk_engine.finish()
        await self.agent.finish()

        await self.send(
            {
                "type": "call_ended",
                "call_id": self.call_id,
                "reason": reason,
                "seconds_received": round(self.seconds_received, 2),
                "bytes_received": self.bytes_received,
                # 0 means silence and 1 is the loudest possible. Helps spot a muted mic.
                "peak_levels": {
                    speaker: round(peak / 32768, 3) for speaker, peak in self.peak_levels.items()
                },
            }
        )
        logger.info("Call ended: %s, %s, peaks %s", self.call_id, reason, self.peak_levels)
        await self.send(
            build_summary(
                self.call_id,
                self.title,
                reason,
                self.seconds_received,
                self.risk_engine,
                self.alerts,
                self.agent,
            )
        )
        self.call_id = None
        self.risk_engine = None
        self.agent = None

    async def handle_audio(self, chunk: bytes) -> None:
        if self.call_id is None:
            await self.send(error("Audio received with no call in progress"))
            return
        if len(chunk) % settings.audio_bytes_per_frame != 0:
            await self.send(error("Audio chunk is not a whole number of stereo frames"))
            return
        if self.limit_reached:
            return

        self.bytes_received += len(chunk)
        self.record_peak_levels(chunk)
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

        self.agent.check_silence(self.seconds_received)
        if self.seconds_received >= settings.max_call_seconds:
            self.limit_reached = True
            await self.send({"type": "call_limit_reached", "seconds": settings.max_call_seconds})

    def record_peak_levels(self, chunk: bytes) -> None:
        samples = array("h")
        samples.frombytes(chunk)
        for speaker, channel in (("caller", samples[0::2]), ("user", samples[1::2])):
            if channel:
                loudest = max(max(channel), -min(channel))
                self.peak_levels[speaker] = max(self.peak_levels[speaker], loudest)

    async def send_segment(self, segment: dict) -> None:
        # Once the agent has taken over, it speaks for the user, so anything the
        # user starts saying after that point is left out.
        took_over_at = self.agent.took_over_at if self.agent else None
        if (
            segment["speaker"] == "user"
            and took_over_at is not None
            and segment["start"] >= took_over_at
        ):
            return

        await self.send_if_connected({"type": "transcript", **segment})
        if self.risk_engine is None:
            return
        if segment["speaker"] == "user":
            await self.agent.on_user_speech(segment["text"], self.seconds_received)
        await self.risk_engine.add_segment(segment)

    async def handle_risk_message(self, message: dict) -> None:
        await self.send_if_connected(message)
        if message["type"] == "risk_update" and self.risk_engine is not None:
            alert = self.alerts.check(message, self.risk_engine.active_categories)
            if alert is not None:
                await self.send_if_connected(alert)
                await self.send_if_connected(
                    trace_event(
                        "alert",
                        alert["time"],
                        id=alert["id"],
                        level=alert["level"],
                        reason=alert["reason"],
                        is_realert=alert["is_realert"],
                        whisper=alert["whisper"],
                    )
                )
                if alert["whisper"]:
                    self.speak_in_background("whisper", alert["whisper"])

    async def dismiss_alert(self, alert_id: object) -> None:
        if self.risk_engine is None:
            await self.send(error("No call in progress"))
            return
        result = self.alerts.dismiss(alert_id, self.seconds_received)
        if result is None:
            await self.send(error(f"Unknown alert: {alert_id}"))
            return

        alert, trace = result
        self.risk_engine.dismiss(alert["categories"])
        await self.send({"type": "alert_dismissed", "alert_id": alert["id"]})
        await self.send(trace)
        await self.risk_engine.send_update("dismissal", self.seconds_received, [], [])

    async def speak(self, kind: str, text: str) -> None:
        await self.send_if_connected(await speech_message(kind, text))

    def speak_in_background(self, kind: str, text: str) -> None:
        # Generating speech takes a moment, and the audio must keep flowing.
        task = asyncio.create_task(self.speak(kind, text))
        self.speech_tasks.add(task)
        task.add_done_callback(self.speech_tasks.discard)

    async def agent_end_call(self, reason: str) -> None:
        await self.send_if_connected({"type": "agent_end_call", "reason": reason})

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

    async def clean_up_call(self) -> None:
        await self.stop_transcriber()
        if self.risk_engine is not None:
            self.risk_engine.cancel()
            self.risk_engine = None
        if self.agent is not None:
            self.agent.cancel()
            self.agent = None
        for task in self.speech_tasks:
            task.cancel()

    async def close(self) -> None:
        """The browser has gone, so clean up without sending anything."""
        self.connected = False
        await self.clean_up_call()
