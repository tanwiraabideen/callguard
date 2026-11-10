"""HTTP and WebSocket routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.auth import authenticate_websocket, require_passcode
from app.call_session import CallSession
from app.calls import audio_path, load_generated_calls

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/calls", dependencies=[Depends(require_passcode)])
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


@router.get("/calls/{call_id}/audio", dependencies=[Depends(require_passcode)])
def call_audio(call_id: str) -> FileResponse:
    # Checking the id against known calls means it can't be used to read other files.
    if call_id not in load_generated_calls():
        raise HTTPException(status_code=404, detail="Unknown call")
    return FileResponse(audio_path(call_id), media_type="audio/wav")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session = CallSession(websocket.send_json)
    try:
        if not await authenticate_websocket(websocket):
            return
        logger.info("WebSocket client connected")
        await websocket.send_json({"type": "connected"})

        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            # A frame holds either binary audio or a JSON text message.
            if message.get("bytes") is not None:
                await session.handle_audio(message["bytes"])
            else:
                await session.handle_text(message["text"])
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()
    logger.info("WebSocket client disconnected")
