"""Decides when the agent runs during a call.

The first trigger phrase gets private advice. A second one, or the user going
silent at high risk, makes the agent take over. Runs happen in the background
so that audio and transcription are never held up.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.agent.graph import run_agent
from app.agent.tools import ADVISE, TAKE_OVER, AgentTools
from app.agent.triggers import TriggerDetector
from app.config import settings
from app.risk.engine import RiskEngine
from app.trace import trace_event
from app.tracing import configure_tracing, run_url

logger = logging.getLogger("uvicorn.error")
configure_tracing()


class AgentController:
    def __init__(
        self,
        engine: RiskEngine,
        speak: Callable[[str, str], Awaitable[None]],
        end_call: Callable[[str], Awaitable[None]],
        send: Callable[[dict], Awaitable[None]],
    ) -> None:
        self.engine = engine
        self.speak = speak
        self.end_call = end_call
        self.send = send
        self.detector = TriggerDetector()
        self.trigger_count = 0
        self.took_over = False
        self.took_over_at: float | None = None
        self.last_user_speech = 0.0
        self.high_risk_since: float | None = None
        self.queue: list[tuple[str, str, float]] = []
        self.task: asyncio.Task | None = None
        self.summary: str | None = None
        self.actions: list[str] = []
        self.langsmith_url: str | None = None

    async def on_user_speech(self, text: str, now: float) -> None:
        self.last_user_speech = now
        if not settings.agent_enabled or self.took_over:
            return
        phrase = self.detector.check(text, now)
        if phrase is None:
            return

        self.trigger_count += 1
        await self.send(trace_event("trigger", now, phrase=phrase, count=self.trigger_count))
        mode = TAKE_OVER if self.trigger_count >= 2 else ADVISE
        self.start(mode, f'The user said "{phrase}" (time {self.trigger_count}).', now)

    def check_silence(self, now: float) -> None:
        if self.engine.level != "high":
            self.high_risk_since = None
            return
        if self.high_risk_since is None:
            self.high_risk_since = now

        quiet_since = max(self.high_risk_since, self.last_user_speech)
        if (
            settings.agent_enabled
            and not self.took_over
            and now - quiet_since >= settings.takeover_silence_seconds
        ):
            self.start(TAKE_OVER, "The user has gone silent at high risk.", now)

    def start(self, mode: str, reason: str, now: float) -> None:
        if mode == TAKE_OVER:
            self.took_over = True
            self.took_over_at = now
        self.queue.append((mode, reason, now))
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run_queue())

    async def run_queue(self) -> None:
        while self.queue:
            mode, reason, now = self.queue.pop(0)
            try:
                await self.run_once(mode, reason, now)
            except Exception as error:
                logger.exception("Agent run failed")
                await self.send(trace_event("agent_error", now, detail=str(error)))

    def build_context(self, reason: str, now: float) -> dict:
        return {
            "reason": reason,
            "time": now,
            "score": round(self.engine.score, 1),
            "level": self.engine.level,
            "categories": self.engine.active_categories,
            "sentences": self.engine.sentences[-settings.agent_context_sentences :],
            "all_caller_text": " ".join(
                s["text"] for s in self.engine.sentences if s["speaker"] == "caller"
            ),
        }

    async def run_once(self, mode: str, reason: str, now: float) -> None:
        await self.send(trace_event("agent_start", now, mode=mode, reason=reason))
        tools = AgentTools(mode, self.speak, self.end_call)
        run_id = uuid4()
        await run_agent(mode, self.build_context(reason, now), tools, self.send, run_id)

        self.actions.extend(sorted(tools.used))
        self.summary = tools.summary or self.summary
        url = await run_url(run_id)
        if url:
            self.langsmith_url = url
        await self.send(
            trace_event("agent_done", now, mode=mode, tools=sorted(tools.used), langsmith_url=url)
        )

    async def finish(self) -> None:
        if self.task is not None and not self.task.done():
            await asyncio.wait({self.task}, timeout=settings.agent_timeout_seconds * 2)
        self.cancel()

    def cancel(self) -> None:
        self.queue.clear()
        if self.task is not None:
            self.task.cancel()
