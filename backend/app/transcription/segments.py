"""The transcript format shared by the real and mock transcribers.

A segment is a stretch of one speaker's words. It is either interim, meaning
it may still change, or final. Times are seconds from the start of the call.
"""

from collections.abc import Awaitable, Callable

OnSegment = Callable[[dict], Awaitable[None]]


class TranscriptionError(Exception):
    """The transcription service could not be used."""


def make_segment(speaker: str, words: list[dict], is_final: bool) -> dict:
    return {
        "speaker": speaker,
        "text": " ".join(word["word"] for word in words),
        "start": words[0]["start"],
        "end": words[-1]["end"],
        "is_final": is_final,
        "words": words,
    }


def make_interim_segment(speaker: str, text: str, start: float) -> dict:
    """An interim segment from a service that only times words once they're final."""
    return {
        "speaker": speaker,
        "text": text,
        "start": start,
        "end": start,
        "is_final": False,
        "words": [],
    }
