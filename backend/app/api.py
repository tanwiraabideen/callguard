"""HTTP and WebSocket routes."""

import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.call_session import CallSession
from app.calls import audio_path, load_generated_calls

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/calls")
def list_calls() -> list[dict]:
    # Only what the picker needs. Scam labels and timings stay on the server.
    return [
        {
            "id": call["id"],
            "title": call["title"],
            "duration_seconds": call["duration_seconds"],
            "sample_rate": call["sample_rate"],
        }
        for call in load_generated_calls().values()
    ]


@router.get("/calls/{call_id}/audio")
def call_audio(call_id: str) -> FileResponse:
    # Checking the id against known calls means it can't be used to read other files.
    if call_id not in load_generated_calls():
        raise HTTPException(status_code=404, detail="Unknown call")
    return FileResponse(audio_path(call_id), media_type="audio/wav")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket client connected")
    await websocket.send_json({"type": "connected"})

    session = CallSession()
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            # A frame holds either binary audio or a JSON text message.
            if message.get("bytes") is not None:
                reply = session.handle_audio(message["bytes"])
            else:
                reply = session.handle_text(message["text"])

            if reply is not None:
                await websocket.send_json(reply)
    except WebSocketDisconnect:
        pass
    logger.info("WebSocket client disconnected")
