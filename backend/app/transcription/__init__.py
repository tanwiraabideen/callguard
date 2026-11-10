"""Picks the real or mock transcriber. Both have the same three methods:
start(), send_audio(chunk) and finish().
"""

from app.config import settings
from app.transcription.elevenlabs import ElevenLabsTranscriber
from app.transcription.mock import MockTranscriber
from app.transcription.segments import OnSegment


def create_transcriber(call: dict, on_segment: OnSegment) -> ElevenLabsTranscriber | MockTranscriber:
    if settings.active_transcription_mode == "elevenlabs":
        return ElevenLabsTranscriber(on_segment)
    return MockTranscriber(call, on_segment)
