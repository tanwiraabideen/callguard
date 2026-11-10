"""Combines rules, voice pressure and the LLM into a running call risk score.

Red flags add points, and each kind of red flag is tracked separately so that
stage 5 can lower one kind when the user dismisses it. The LLM's opinion is
blended with those points to give a target. The score then moves part of the
way to the target on each sentence, so it builds over a call instead of spiking
on one sentence.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.config import settings
from app.risk.llm import assess_sentences
from app.risk.pressure import PressureTracker
from app.risk.rules import find_rule_hits

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
    def __init__(self, on_update: Callable[[dict], Awaitable[None]]) -> None:
        self.on_update = on_update
        self.pressure = PressureTracker()
        self.sentences: list[dict] = []
        self.rule_points: dict[str, float] = {}
        self.pressure_points = 0.0
        self.score = 0.0
        self.llm_result: dict | None = None
        self.llm_task: asyncio.Task | None = None
        self.llm_rerun = False
        self.llm_error_reported = False
        self.latest_labels: list[str] = []

    @property
    def evidence(self) -> float:
        return min(100.0, sum(self.rule_points.values()) + self.pressure_points)

    @property
    def target(self) -> float:
        if self.llm_result is None:
            return self.evidence
        weight = settings.llm_weight
        return (1 - weight) * self.evidence + weight * self.llm_result["score"]

    def move_score_towards_target(self) -> None:
        difference = self.target - self.score
        rate = settings.risk_rise_rate if difference > 0 else settings.risk_fall_rate
        self.score += rate * difference

    def add_rule_hit(self, hit: dict) -> None:
        category = hit["category"]
        points = hit["weight"]
        if category in self.rule_points:
            points *= settings.rule_repeat_factor
        self.rule_points[category] = self.rule_points.get(category, 0.0) + points

    async def add_segment(self, segment: dict) -> None:
        if segment["is_final"]:
            for sentence in split_into_sentences(segment):
                await self.add_sentence(sentence)

    async def add_sentence(self, sentence: dict) -> None:
        self.sentences.append(sentence)
        is_caller = sentence["speaker"] == "caller"
        signals = self.pressure.add_sentence(sentence)
        hits = find_rule_hits(sentence["text"]) if is_caller else []

        for hit in hits:
            self.add_rule_hit(hit)
        for fired in signals:
            self.pressure_points = min(
                settings.pressure_points_cap, self.pressure_points + fired["weight"]
            )
        if hits or signals:
            self.latest_labels = [item["label"] for item in hits + signals]

        if is_caller or signals:
            self.move_score_towards_target()
            await self.send_update("sentence", sentence["end"], hits, signals)

        # Tier 2 only runs when Tier 1 or a pressure signal has something to check.
        if (hits or signals) and settings.llm_active:
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
            context = self.sentences[-settings.llm_context_sentences :]
            try:
                self.llm_result = await assess_sentences(context)
            except Exception as error:
                logger.warning("LLM check failed: %s", error)
                await self.report_llm_error(error)
            else:
                self.move_score_towards_target()
                await self.send_update("llm", context[-1]["end"], [], [])
            if not self.llm_rerun:
                return

    async def report_llm_error(self, error: Exception) -> None:
        if not self.llm_error_reported:
            self.llm_error_reported = True
            await self.on_update(
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

        await self.on_update(
            {
                "type": "risk_update",
                "source": source,
                "time": time,
                "score": round(self.score, 1),
                "level": level_for(self.score),
                "reason": reason,
                "rules": hits,
                "pressure": signals,
                "llm": self.llm_result if source == "llm" else None,
            }
        )

    async def finish(self) -> None:
        """Wait for any LLM check in progress, so the final score includes it."""
        if self.llm_task is not None and not self.llm_task.done():
            await asyncio.wait({self.llm_task}, timeout=settings.llm_timeout_seconds * 2)
        self.cancel()

    def cancel(self) -> None:
        if self.llm_task is not None:
            self.llm_task.cancel()
