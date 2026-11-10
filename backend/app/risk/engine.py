"""Combines rules, voice pressure and the LLM into a running call risk score.

Red flags add points, and each kind of red flag is tracked separately so that
a dismissal can lower just that kind. The LLM's opinion is blended with those
points to give a target. The score then moves part of the way to the target on
each sentence, so it builds over a call instead of spiking on one sentence.
"""

import asyncio
import logging
import time as clock
from collections.abc import Awaitable, Callable

from app.config import settings
from app.risk.llm import assess_sentences
from app.risk.pressure import PressureTracker
from app.risk.rules import find_rule_hits
from app.trace import trace_event

logger = logging.getLogger("uvicorn.error")


def split_into_sentences(segment: dict) -> list[dict]:
    """Split a final segment, because a transcriber may join several sentences."""
    sentences = []
    current: list[dict] = []
    for index, word in enumerate(segment["words"]):
        current.append(word)
        if word["word"][-1] in ".?!" or index == len(segment["words"]) - 1:
            sentences.append(
                {
                    "speaker": segment["speaker"],
                    "text": " ".join(w["word"] for w in current),
                    "start": current[0]["start"],
                    "end": current[-1]["end"],
                    "words": current,
                }
            )
            current = []
    return sentences


def level_for(score: float) -> str:
    if score >= settings.risk_high_threshold:
        return "high"
    if score >= settings.risk_medium_threshold:
        return "medium"
    return "low"


class RiskEngine:
    def __init__(self, on_message: Callable[[dict], Awaitable[None]]) -> None:
        self.on_message = on_message
        self.pressure = PressureTracker()
        self.sentences: list[dict] = []
        self.rule_points: dict[str, float] = {}
        self.pressure_points = 0.0
        self.dismissed: set[str] = set()
        self.score = 0.0
        self.peak_score = 0.0
        self.flag_events: list[dict] = []
        self.latest_labels: list[str] = []
        self.llm_result: dict | None = None
        self.llm_task: asyncio.Task | None = None
        self.llm_rerun = False
        self.llm_error_reported = False
        self.llm_generation = 0  # bumped by a dismissal, to discard older answers

    @property
    def evidence(self) -> float:
        return min(100.0, sum(self.rule_points.values()) + self.pressure_points)

    @property
    def target(self) -> float:
        if self.llm_result is None:
            return self.evidence
        weight = settings.llm_weight
        return (1 - weight) * self.evidence + weight * self.llm_result["score"]

    @property
    def level(self) -> str:
        return level_for(self.score)

    @property
    def active_categories(self) -> list[str]:
        return [category for category in self.rule_points if category not in self.dismissed]

    def move_score_towards_target(self) -> None:
        difference = self.target - self.score
        rate = settings.risk_rise_rate if difference > 0 else settings.risk_fall_rate
        self.score += rate * difference
        self.peak_score = max(self.peak_score, self.score)

    def add_rule_hit(self, hit: dict, time: float) -> None:
        category = hit["category"]
        hit["suppressed"] = category in self.dismissed
        self.flag_events.append({**hit, "time": time})
        if hit["suppressed"]:
            return

        points = hit["weight"]
        if category in self.rule_points:
            points *= settings.rule_repeat_factor
        self.rule_points[category] = self.rule_points.get(category, 0.0) + points

    def dismiss(self, categories: list[str]) -> None:
        """Lower these red flags and ignore repeats of them from now on."""
        for category in categories:
            self.dismissed.add(category)
            if category in self.rule_points:
                self.rule_points[category] *= settings.dismiss_points_factor
        self.llm_result = None
        self.llm_generation += 1
        self.score = min(self.score, self.target)

    async def add_segment(self, segment: dict) -> None:
        if segment["is_final"]:
            for sentence in split_into_sentences(segment):
                await self.add_sentence(sentence)

    async def add_sentence(self, sentence: dict) -> None:
        started = clock.perf_counter()
        self.sentences.append(sentence)
        is_caller = sentence["speaker"] == "caller"
        signals = self.pressure.add_sentence(sentence)
        hits = find_rule_hits(sentence["text"]) if is_caller else []
        check_ms = round((clock.perf_counter() - started) * 1000, 2)

        for hit in hits:
            self.add_rule_hit(hit, sentence["end"])
        for fired in signals:
            self.flag_events.append({**fired, "category": fired["signal"], "time": sentence["end"]})
            self.pressure_points = min(
                settings.pressure_points_cap, self.pressure_points + fired["weight"]
            )

        active_hits = [hit for hit in hits if not hit["suppressed"]]
        if active_hits or signals:
            self.latest_labels = [item["label"] for item in active_hits + signals]

        if is_caller or signals:
            self.move_score_towards_target()

        await self.on_message(
            trace_event(
                "sentence",
                sentence["end"],
                speaker=sentence["speaker"],
                text=sentence["text"],
                rules=hits,
                pressure=signals,
                score=round(self.score, 1),
                check_ms=check_ms,
            )
        )
        if is_caller or signals:
            await self.send_update("sentence", sentence["end"], hits, signals)

        # Tier 2 only runs when Tier 1 or a pressure signal has something to check.
        if (active_hits or signals) and settings.llm_active:
            self.request_llm()

    def request_llm(self) -> None:
        # One request at a time. Anything newer is covered by a single rerun.
        if self.llm_task is not None and not self.llm_task.done():
            self.llm_rerun = True
        else:
            self.llm_task = asyncio.create_task(self.run_llm())

    async def run_llm(self) -> None:
        while True:
            self.llm_rerun = False
            generation = self.llm_generation
            context = self.sentences[-settings.llm_context_sentences :]
            try:
                result = await assess_sentences(context)
            except Exception as error:
                logger.warning("LLM check failed: %s", error)
                await self.report_llm_error(error, context[-1]["end"])
            else:
                if generation == self.llm_generation:
                    self.llm_result = result
                    self.move_score_towards_target()
                    await self.on_message(
                        trace_event(
                            "llm", context[-1]["end"], risk_after=round(self.score, 1), **result
                        )
                    )
                    await self.send_update("llm", context[-1]["end"], [], [])
            if not self.llm_rerun:
                return

    async def report_llm_error(self, error: Exception, time: float) -> None:
        await self.on_message(trace_event("llm_error", time, detail=str(error)))
        if not self.llm_error_reported:
            self.llm_error_reported = True
            await self.on_message(
                {"type": "error", "detail": f"LLM check failed, using rules only: {error}"}
            )

    async def send_update(
        self, source: str, time: float, hits: list[dict], signals: list[dict]
    ) -> None:
        if self.llm_result is not None:
            reason = self.llm_result["reason"]
        elif self.latest_labels:
            reason = "Caller " + "; ".join(
                label.removeprefix("caller ") for label in self.latest_labels
            )
        else:
            reason = "No red flags so far"

        await self.on_message(
            {
                "type": "risk_update",
                "source": source,
                "time": time,
                "score": round(self.score, 1),
                "level": self.level,
                "reason": reason,
                "rules": hits,
                "pressure": signals,
            }
        )

    async def wait_for_llm(self) -> None:
        """Used by the evaluation, which runs faster than real time."""
        while self.llm_task is not None and not self.llm_task.done():
            await asyncio.sleep(0.01)

    async def finish(self) -> None:
        """Wait for any LLM check in progress, so the final score includes it."""
        if self.llm_task is not None and not self.llm_task.done():
            await asyncio.wait({self.llm_task}, timeout=settings.llm_timeout_seconds * 2)
        self.cancel()

    def cancel(self) -> None:
        if self.llm_task is not None:
            self.llm_task.cancel()
