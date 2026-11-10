"""Spots the natural phrases the user says to ask for help without touching a screen."""

import re

from app.config import settings


def normalise(text: str) -> str:
    return " ".join(re.sub(r"[^a-z' ]", " ", text.lower()).split())


class TriggerDetector:
    def __init__(self) -> None:
        self.phrases = [normalise(phrase) for phrase in settings.trigger_phrase_list]
        self.last_trigger_time: float | None = None

    def check(self, text: str, now: float) -> str | None:
        """Return the phrase if newly heard. Partial and final text of one
        utterance both pass through here, so a cooldown stops it counting twice.
        """
        cooling_down = (
            self.last_trigger_time is not None
            and now - self.last_trigger_time < settings.trigger_cooldown_seconds
        )
        if cooling_down:
            return None

        heard = normalise(text)
        for phrase in self.phrases:
            if phrase in heard:
                self.last_trigger_time = now
                return phrase
        return None
