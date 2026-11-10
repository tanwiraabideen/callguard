"""Replays a call's known transcript instead of calling a speech-to-text service.

The incoming audio is the clock: a word is released once enough audio has
arrived to cover it. So the words follow the stream, and stop if the call stops.
"""

from app.config import settings
from app.transcription.segments import OnSegment, make_segment


def flatten_words(call: dict) -> list[dict]:
    """Return every word in the call, in the order the words finish."""
    words = []
    for turn in call["turns"]:
        last_index = len(turn["words"]) - 1
        for index, word in enumerate(turn["words"]):
            ends_sentence = index == last_index or word["word"][-1] in ".?!"
            words.append({**word, "speaker": turn["speaker"], "ends_sentence": ends_sentence})
    return sorted(words, key=lambda word: word["end"])


class MockTranscriber:
    def __init__(self, call: dict, on_segment: OnSegment) -> None:
        self.words = flatten_words(call)
        self.on_segment = on_segment
        self.next_word = 0
        self.seconds_received = 0.0
        self.unfinished: dict[str, list[dict]] = {"caller": [], "user": []}

    async def start(self) -> None:
        pass

    async def send_audio(self, chunk: bytes) -> None:
        self.seconds_received += len(chunk) / settings.audio_bytes_per_second

        speakers_with_new_words = set()
        while self.next_word < len(self.words):
            word = self.words[self.next_word]
            if word["end"] > self.seconds_received:
                break
            self.next_word += 1

            speaker = word["speaker"]
            self.unfinished[speaker].append(
                {"word": word["word"], "start": word["start"], "end": word["end"]}
            )
            if word["ends_sentence"]:
                await self.send_final(speaker)
                speakers_with_new_words.discard(speaker)
            else:
                speakers_with_new_words.add(speaker)

        for speaker in speakers_with_new_words:
            await self.on_segment(make_segment(speaker, self.unfinished[speaker], False))

    async def send_final(self, speaker: str) -> None:
        await self.on_segment(make_segment(speaker, self.unfinished[speaker], True))
        self.unfinished[speaker] = []

    async def finish(self) -> None:
        # A call stopped early can leave a sentence half said.
        for speaker, words in self.unfinished.items():
            if words:
                await self.send_final(speaker)
