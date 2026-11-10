"""Voice pressure signals, worked out from word timestamps.

Fast speech and talk share fire once each time they become true, so a caller
who keeps talking doesn't fire on every sentence. Each interruption fires once.
"""

from app.config import settings


def signal(name: str, label: str, weight: float, value: float) -> dict:
    return {"signal": name, "label": label, "weight": weight, "value": round(value, 2)}


class PressureTracker:
    def __init__(self) -> None:
        self.sentences: list[dict] = []
        self.interrupting_starts: set[float] = set()
        self.was_fast = False
        self.was_dominant = False

    def add_sentence(self, sentence: dict) -> list[dict]:
        """Record one final sentence and return any signals that just fired."""
        self.sentences.append(sentence)
        signals = self.find_interruptions(sentence)
        if sentence["speaker"] == "caller":
            signals += self.check_speaking_rate(sentence["end"])
            signals += self.check_talk_share(sentence["end"])
        return signals

    def recent(self, speaker: str, now: float) -> list[dict]:
        cutoff = now - settings.pressure_window_seconds
        return [s for s in self.sentences if s["speaker"] == speaker and s["end"] >= cutoff]

    def find_interruptions(self, sentence: dict) -> list[dict]:
        """A caller interrupts by starting while the user's sentence is underway.

        Each speaker is transcribed separately, so either sentence can arrive
        first. That's why both directions are checked.
        """
        if sentence["speaker"] == "caller":
            pairs = [(sentence, s) for s in self.sentences if s["speaker"] == "user"]
        else:
            pairs = [(s, sentence) for s in self.sentences if s["speaker"] == "caller"]

        signals = []
        for caller, user in pairs:
            overlap = user["end"] - caller["start"]
            is_interruption = (
                user["start"] < caller["start"]
                and overlap >= settings.pressure_interruption_min_overlap_seconds
            )
            if is_interruption and caller["start"] not in self.interrupting_starts:
                self.interrupting_starts.add(caller["start"])
                signals.append(
                    signal(
                        "interruption",
                        "caller talked over the user",
                        settings.pressure_weight_interruption,
                        overlap,
                    )
                )
        return signals

    def check_speaking_rate(self, now: float) -> list[dict]:
        sentences = self.recent("caller", now)
        words = sum(len(s["words"]) for s in sentences)
        speech_seconds = sum(s["end"] - s["start"] for s in sentences)
        if words < settings.pressure_min_caller_words or speech_seconds <= 0:
            return []

        words_per_minute = words / speech_seconds * 60
        is_fast = words_per_minute >= settings.pressure_fast_wpm
        just_started = is_fast and not self.was_fast
        self.was_fast = is_fast
        if not just_started:
            return []
        return [
            signal(
                "fast_speech",
                "caller is speaking unusually fast",
                settings.pressure_weight_fast_speech,
                words_per_minute,
            )
        ]

    def check_talk_share(self, now: float) -> list[dict]:
        caller = self.recent("caller", now)
        user = self.recent("user", now)
        if sum(len(s["words"]) for s in caller) < settings.pressure_min_caller_words:
            return []

        caller_seconds = sum(s["end"] - s["start"] for s in caller)
        user_seconds = sum(s["end"] - s["start"] for s in user)
        share = caller_seconds / (caller_seconds + user_seconds)
        is_dominant = share >= settings.pressure_talk_share
        just_started = is_dominant and not self.was_dominant
        self.was_dominant = is_dominant
        if not just_started:
            return []
        return [
            signal(
                "talk_share",
                "caller is dominating the conversation",
                settings.pressure_weight_talk_share,
                share,
            )
        ]
