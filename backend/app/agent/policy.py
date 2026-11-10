"""The agent's fixed plan, used when Claude isn't available or stops early.

It goes through the same graph and tools as Claude. It returns the next tool
still to be done, so it can also finish a job that Claude started.
"""

import re

from app.agent.tools import TAKE_OVER, find_official_number
from app.risk.alerts import whisper_for

CHECK_AGAINST = {"HMRC": "HMRC", "bank": "your bank"}


def guess_organisation(context: dict) -> str:
    """Which organisation the caller claims to be. Report Fraud if it's unclear."""
    text = context["all_caller_text"]
    if re.search(r"\b(hmrc|hm revenue|revenue (and|&) customs|tax)\b", text, re.IGNORECASE):
        return "HMRC"
    if re.search(r"\bbank\b", text, re.IGNORECASE):
        return "bank"
    return "Report Fraud"


def advice_for(context: dict, organisation: str) -> str:
    if context["level"] == "low":
        return "No clear warning signs so far. Never share codes or move money."

    warning = whisper_for(context["categories"])
    if organisation in CHECK_AGAINST:
        number = find_official_number(organisation)["number"]
        return f"{warning} To reach {CHECK_AGAINST[organisation]}, call {number}."
    return f"{warning} Only call back on a number you already trust."


def next_policy_call(mode: str, used: set[str], context: dict) -> dict | None:
    organisation = guess_organisation(context)

    if mode == TAKE_OVER:
        plan = [
            ("lookup_official_number", {"organisation": organisation}),
            (
                "say_to_caller",
                {"text": "I won't be continuing this call. I'll ring back on the official number. "
                 "Goodbye."},
            ),
            (
                "write_summary",
                {"summary": f"The call reached {context['level']} risk, so the agent spoke for "
                 "you and ended it."},
            ),
            ("end_call", {"reason": "High risk of a scam."}),
        ]
    else:
        plan = [
            ("lookup_official_number", {"organisation": organisation}),
            ("whisper_to_user", {"text": advice_for(context, organisation)}),
        ]

    for name, arguments in plan:
        if name not in used:
            return {"name": name, "input": arguments}
    return None
