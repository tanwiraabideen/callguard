"""Tracks one browser's connection: its messages and the call audio it sends.

Audio arrives as binary frames of 16-bit stereo samples, left = caller and
right = user. For now it is only counted. Stage 3 sends it to transcription.
"""

import json
import logging
import time

from app.calls import load_generated_calls
from app.config import settings

logger = logging.getLogger("uvicorn.error")

BYTES_PER_FRAME = 2 * settings.audio_channels  # 2 bytes per sample, per channel
BYTES_PER_SECOND = settings.audio_sample_rate * BYTES_PER_FRAME


def error(detail: str) -> dict:
    return {"type": "error", "detail": detail}


class CallSession:
    def __init__(self) -> None:
        self.call_id: str | None = None
        self.bytes_received = 0
        self.next_progress_seconds = 0.0

    @property
    def seconds_received(self) -> float:
        return self.bytes_received / BYTES_PER_SECOND

    def handle_text(self, raw: str) -> dict:
        """Turn one incoming JSON message into the message to send back."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return error("Message must be valid JSON")

        if not isinstance(message, dict):
            return error("Message must be a JSON object")

        message_type = message.get("type")
        if message_type == "ping":
            # sent_at is echoed so the browser can measure the round trip.
            return {
                "type": "pong",
                "sent_at": message.get("sent_at"),
                "server_time": time.time(),
            }
        if message_type == "call_start":
            return self.start_call(message.get("call_id"))
        if message_type == "call_end":
            return self.end_call(message.get("reason", "unknown"))

        return error(f"Unknown message type: {message_type}")

    def start_call(self, call_id: object) -> dict:
        if not isinstance(call_id, str) or call_id not in load_generated_calls():
            return error(f"Unknown call: {call_id}")

        self.call_id = call_id
        self.bytes_received = 0
        self.next_progress_seconds = settings.audio_progress_interval_seconds
        logger.info("Call started: %s", call_id)
        return {"type": "call_started", "call_id": call_id}

    def end_call(self, reason: object) -> dict:
        if self.call_id is None:
            return error("No call in progress")

        reply = {
            "type": "call_ended",
            "call_id": self.call_id,
            "reason": reason,
            "seconds_received": round(self.seconds_received, 2),
            "bytes_received": self.bytes_received,
        }
        logger.info("Call ended: %s", reply)
        self.call_id = None
        return reply

    def handle_audio(self, chunk: bytes) -> dict | None:
        """Count one audio chunk. Returns a message only when one is due."""
        if self.call_id is None:
            return error("Audio received with no call in progress")
        if len(chunk) % BYTES_PER_FRAME != 0:
            return error("Audio chunk is not a whole number of stereo frames")

        self.bytes_received += len(chunk)
        if self.seconds_received < self.next_progress_seconds:
            return None

        self.next_progress_seconds += settings.audio_progress_interval_seconds
        return {
            "type": "audio_progress",
            "seconds_received": round(self.seconds_received, 2),
        }
