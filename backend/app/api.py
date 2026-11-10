"""HTTP and WebSocket routes."""

import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


def build_reply(raw: str) -> dict:
    """Turn one incoming text frame into the message to send back."""
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return {"type": "error", "detail": "Message must be valid JSON"}

    if not isinstance(message, dict):
        return {"type": "error", "detail": "Message must be a JSON object"}

    if message.get("type") == "ping":
        # sent_at is echoed so the browser can measure the round trip.
        return {
            "type": "pong",
            "sent_at": message.get("sent_at"),
            "server_time": time.time(),
        }

    return {"type": "error", "detail": f"Unknown message type: {message.get('type')}"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket client connected")
    await websocket.send_json({"type": "connected"})

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except KeyError:  # Starlette raises this for binary frames
                await websocket.send_json({"type": "error", "detail": "Text frames only"})
                continue
            await websocket.send_json(build_reply(raw))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
