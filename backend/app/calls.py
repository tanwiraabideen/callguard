"""Finds the call scripts and their generated audio on disk.

Each call has three files:
  calls/scripts/<id>.json           the script, written by hand
  calls/generated/<id>.wav          stereo audio, left = caller, right = user
  calls/generated/<id>.timing.json  when each turn and word is spoken
"""

import json
from pathlib import Path

from app.config import BACKEND_DIR

SCRIPTS_DIR = BACKEND_DIR / "calls" / "scripts"
GENERATED_DIR = BACKEND_DIR / "calls" / "generated"


def audio_path(call_id: str) -> Path:
    return GENERATED_DIR / f"{call_id}.wav"


def timing_path(call_id: str) -> Path:
    return GENERATED_DIR / f"{call_id}.timing.json"


def load_scripts() -> list[dict]:
    paths = sorted(SCRIPTS_DIR.glob("*.json"))
    return [json.loads(path.read_text()) for path in paths]


def load_generated_calls() -> dict[str, dict]:
    """Return every call that has audio, keyed by call id."""
    calls = {}
    for path in sorted(GENERATED_DIR.glob("*.timing.json")):
        call = json.loads(path.read_text())
        calls[call["id"]] = call
    return calls
