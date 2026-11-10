"""Runs every call through the detection pipeline in mock mode and reports the results.

Usage, from the backend folder:
  uv run python -m tools.evaluate                 use the LLM check if a key is set
  uv run python -m tools.evaluate --rules-only    rules and voice pressure only

Calls run faster than real time, using silence as the clock for the mock
transcript. The run waits for each LLM answer before moving on, so the times
measure when the audio triggered an alert and leave out the LLM's own delay.
"""

import argparse
import asyncio
import json
import math
from pathlib import Path

from app.call_session import CallSession
from app.calls import load_generated_calls
from app.config import BACKEND_DIR, settings

RESULTS_DIR = BACKEND_DIR / "eval"
CHUNK_SECONDS = 0.1


def first_red_flag_time(call: dict) -> float | None:
    for turn in call["turns"]:
        if turn.get("first_red_flag"):
            return turn["start"]
    return None


async def evaluate_call(call: dict) -> dict:
    messages: list[dict] = []

    async def collect(message: dict) -> None:
        messages.append(message)

    session = CallSession(collect)
    await session.handle_text(json.dumps({"type": "call_start", "call_id": call["id"]}))

    silence = bytes(int(settings.audio_bytes_per_second * CHUNK_SECONDS))
    silence = silence[: len(silence) - len(silence) % settings.audio_bytes_per_frame]
    for _ in range(math.ceil(call["duration_seconds"] / CHUNK_SECONDS)):
        await session.handle_audio(silence)
        await session.risk_engine.wait_for_llm()
    await session.handle_text(json.dumps({"type": "call_end", "reason": "finished"}))

    alerts = [m for m in messages if m["type"] == "alert"]
    updates = [m for m in messages if m["type"] == "risk_update"]
    red_flag = first_red_flag_time(call)
    first_alert = alerts[0]["time"] if alerts else None
    delay = None
    if red_flag is not None and first_alert is not None:
        delay = round(first_alert - red_flag, 1)

    return {
        "id": call["id"],
        "title": call["title"],
        "label": call["label"],
        "flagged": bool(alerts),
        "first_red_flag": red_flag,
        "first_alert": round(first_alert, 1) if first_alert is not None else None,
        "delay_seconds": delay,
        "alerts": len(alerts),
        "reached_high": any(alert["level"] == "high" for alert in alerts),
        "peak_score": max((update["score"] for update in updates), default=0.0),
        "correct": bool(alerts) == (call["label"] == "scam"),
    }


def display(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def format_table(results: list[dict]) -> str:
    headers = [
        "Call",
        "Label",
        "Flagged",
        "First red flag (s)",
        "First alert (s)",
        "Delay (s)",
        "Alerts",
        "Reached high",
        "Peak score",
        "Correct",
    ]
    fields = [
        "id",
        "label",
        "flagged",
        "first_red_flag",
        "first_alert",
        "delay_seconds",
        "alerts",
        "reached_high",
        "peak_score",
        "correct",
    ]
    rows = [[display(result[field]) for field in fields] for result in results]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def summarise(results: list[dict]) -> dict:
    scams = [r for r in results if r["label"] == "scam"]
    legit = [r for r in results if r["label"] == "legit"]
    delays = [r["delay_seconds"] for r in scams if r["delay_seconds"] is not None]
    return {
        "scams_flagged": sum(r["flagged"] for r in scams),
        "scams_total": len(scams),
        "legit_calls_with_false_alerts": sum(r["flagged"] for r in legit),
        "false_alerts_total": sum(r["alerts"] for r in legit),
        "legit_total": len(legit),
        "mean_delay_seconds": round(sum(delays) / len(delays), 1) if delays else None,
        "worst_delay_seconds": max(delays) if delays else None,
    }


def format_summary(summary: dict, detection: str) -> str:
    return (
        f"Detection: {detection}\n"
        f"Scams flagged: {summary['scams_flagged']} of {summary['scams_total']}\n"
        f"Legitimate calls with a false alert: {summary['legit_calls_with_false_alerts']} of "
        f"{summary['legit_total']} ({summary['false_alerts_total']} alerts in total)\n"
        f"Delay from first red flag to first alert: mean {summary['mean_delay_seconds']}s, "
        f"worst {summary['worst_delay_seconds']}s"
    )


def save(stem: Path, results: list[dict], summary: dict, table: str, text: str) -> None:
    stem.parent.mkdir(exist_ok=True)
    stem.with_suffix(".json").write_text(
        json.dumps({"summary": summary, "calls": results}, indent=2) + "\n"
    )
    stem.with_suffix(".md").write_text(f"# Evaluation results\n\n{text}\n\n{table}\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-only", action="store_true", help="turn off the LLM check")
    args = parser.parse_args()

    # Detection is what's being measured, and the agent and speech cost money.
    settings.transcription_mode = "mock"
    settings.agent_enabled = False
    settings.speech_enabled = False
    if args.rules_only:
        settings.llm_enabled = False

    calls = load_generated_calls()
    results = [await evaluate_call(call) for call in calls.values()]
    detection = f"rules, voice pressure and {settings.llm_model}" if settings.llm_active else (
        "rules and voice pressure only"
    )
    summary = summarise(results)
    table = format_table(results)
    text = format_summary(summary, detection)

    print(table)
    print()
    print(text)
    stem = RESULTS_DIR / ("results_rules_only" if args.rules_only else "results")
    save(stem, results, summary, table, text)
    print(f"\nSaved to {stem}.md and {stem.name}.json")


if __name__ == "__main__":
    asyncio.run(main())
