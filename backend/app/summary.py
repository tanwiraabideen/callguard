"""Builds the card shown on screen after a call."""

from app.agent.controller import AgentController
from app.risk.alerts import AlertManager
from app.risk.engine import RiskEngine, level_for

NEXT_STEPS = {
    "high": [
        "Don't do anything the caller asked, and don't call back on a number they gave.",
        "To check with your bank, call 159 or the number on your card.",
        "If you shared details or moved money, tell your bank straight away.",
        "Report it to Report Fraud on 0300 123 2040.",
    ],
    "medium": [
        "If you're unsure, hang up and call the organisation on a number you trust.",
        "Never share a code or PIN over the phone.",
    ],
    "low": ["No action needed."],
}


def group_flags(events: list[dict]) -> list[dict]:
    flags: dict[str, dict] = {}
    for event in events:
        flag = flags.setdefault(
            event["category"], {"label": event["label"], "first_time": event["time"], "count": 0}
        )
        flag["count"] += 1
    return sorted(flags.values(), key=lambda flag: flag["first_time"])


def build_summary(
    call_id: str,
    title: str,
    reason: object,
    seconds: float,
    engine: RiskEngine,
    alerts: AlertManager,
    agent: AgentController,
) -> dict:
    peak_level = level_for(engine.peak_score)
    flags = group_flags(engine.flag_events)
    default_text = (
        f"The call lasted {seconds:.0f} seconds and peaked at {peak_level} risk, "
        f"with {len(flags)} kinds of warning sign."
    )
    return {
        "type": "call_summary",
        "call_id": call_id,
        "title": title,
        "ended_by": reason,
        "seconds": round(seconds, 1),
        "final_score": round(engine.score, 1),
        "peak_score": round(engine.peak_score, 1),
        "peak_level": peak_level,
        "what_happened": agent.summary or default_text,
        "red_flags": flags,
        "alerts": len(alerts.alerts),
        "dismissed": alerts.dismissals,
        "agent_actions": agent.actions,
        "next_steps": NEXT_STEPS[peak_level],
        "langsmith_url": agent.langsmith_url,
    }
