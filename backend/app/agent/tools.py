"""The actions the agent can take during a call."""

import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.config import settings

OFFICIAL_NUMBERS = json.loads((Path(__file__).parent / "official_numbers.json").read_text())

ADVISE = "advise"
TAKE_OVER = "take_over"


def text_tool(name: str, description: str, field: str, field_description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {field: {"type": "string", "description": field_description}},
            "required": [field],
            "additionalProperties": False,
        },
    }


TOOL_SCHEMAS = [
    text_tool(
        "whisper_to_user",
        "Speak short advice that only the user hears. The caller never hears it.",
        "text",
        "At most 15 words of plain, calm advice.",
    ),
    text_tool(
        "say_to_caller",
        "Speak to the caller on the user's behalf. Only allowed when taking over.",
        "text",
        "One or two polite, firm sentences. Never reveal that a scam was detected.",
    ),
    text_tool(
        "end_call",
        "Hang up the call. Only allowed when taking over.",
        "reason",
        "Why the call is being ended.",
    ),
    text_tool(
        "lookup_official_number",
        "Find an organisation's published phone number. Never give a number from anywhere else.",
        "organisation",
        "For example HMRC, bank, or Report Fraud.",
    ),
    text_tool(
        "write_summary",
        "Record what happened on the call, for the screen after the call.",
        "summary",
        "Two or three plain sentences, stating only what was said on the call.",
    ),
]


def shorten_whisper(text: str) -> str:
    """Keep a whisper short enough to take in mid-call.

    Sentences go from the front first, unless they hold a phone number, because
    the action at the end matters more than the warning before it.
    """
    limit = settings.whisper_max_words
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    def word_count() -> int:
        return sum(len(sentence.split()) for sentence in sentences)

    index = 0
    while word_count() > limit and index < len(sentences):
        if len(sentences) > 1 and not re.search(r"\d", sentences[index]):
            sentences.pop(index)
        else:
            index += 1

    return " ".join(" ".join(sentences).split()[:limit])


def find_official_number(organisation: str) -> dict:
    wanted = organisation.lower()
    for entry in OFFICIAL_NUMBERS:
        if any(alias in wanted for alias in entry["aliases"]):
            return {"found": True, "name": entry["name"], "number": entry["number"],
                    "note": entry["note"], "source": entry["source"]}
    return {
        "found": False,
        "advice": "No published number on file. Use one from an official letter, bill or website, "
        "and never one the caller gives.",
    }


class AgentTools:
    def __init__(
        self,
        mode: str,
        speak: Callable[[str, str], Awaitable[None]],
        end_call: Callable[[str], Awaitable[None]],
    ) -> None:
        self.mode = mode
        self.speak = speak
        self.request_end_call = end_call
        self.used: set[str] = set()
        self.summary: str | None = None
        self.ended = False

    async def run(self, name: str, arguments: dict) -> dict:
        self.used.add(name)
        if name in ("say_to_caller", "end_call") and self.mode != TAKE_OVER:
            return {"error": f"{name} is only allowed when taking over the call."}

        if name == "whisper_to_user":
            spoken = shorten_whisper(arguments["text"])
            await self.speak("whisper", spoken)
            return {"spoken_to": "user only", "text": spoken}
        if name == "say_to_caller":
            await self.speak("to_caller", arguments["text"])
            return {"spoken_to": "caller"}
        if name == "end_call":
            self.ended = True
            await self.request_end_call(arguments["reason"])
            return {"call_ended": True}
        if name == "lookup_official_number":
            return find_official_number(arguments["organisation"])
        if name == "write_summary":
            self.summary = arguments["summary"]
            return {"saved": True}
        return {"error": f"Unknown tool: {name}"}
