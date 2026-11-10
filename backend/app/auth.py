"""The demo passcode, which stops strangers from spending the API credits.

With DEMO_PASSCODE unset, as it is locally, nothing is checked.
"""

import asyncio
import json
import secrets

from fastapi import Header, HTTPException, WebSocket

from app.config import settings

UNAUTHORISED_CLOSE_CODE = 4401


def passcode_matches(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return secrets.compare_digest(value.encode(), settings.demo_passcode.encode())


def require_passcode(x_demo_passcode: str = Header(default="")) -> None:
    """Used on HTTP routes. The browser sends the passcode in a header."""
    if settings.demo_passcode and not passcode_matches(x_demo_passcode):
        raise HTTPException(status_code=401, detail="Wrong or missing passcode")


async def read_passcode(websocket: WebSocket) -> object:
    """The first WebSocket message must be {"type": "auth", "passcode": "..."}."""
    try:
        message = await asyncio.wait_for(
            websocket.receive(), timeout=settings.auth_timeout_seconds
        )
        data = json.loads(message["text"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    if isinstance(data, dict) and data.get("type") == "auth":
        return data.get("passcode")
    return None


async def authenticate_websocket(websocket: WebSocket) -> bool:
    if not settings.demo_passcode:
        return True

    await websocket.send_json({"type": "auth_required"})
    try:
        passcode = await read_passcode(websocket)
    except TimeoutError:
        # Nobody has typed anything yet, which isn't a failed attempt. The
        # page reconnects by itself and keeps showing the form.
        await websocket.close(code=UNAUTHORISED_CLOSE_CODE)
        return False

    if passcode_matches(passcode):
        return True

    await asyncio.sleep(settings.auth_failure_delay_seconds)  # slows down guessing
    await websocket.send_json({"type": "auth_failed"})
    await websocket.close(code=UNAUTHORISED_CLOSE_CODE)
    return False
