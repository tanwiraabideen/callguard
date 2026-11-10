"""Turns the whisper and the agent's voice into audio for the browser.

If there is no ElevenLabs key, or the request fails, audio_base64 is None and
the browser reads the text aloud with its own built-in voice.
"""

import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger("uvicorn.error")

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
VOICES = {
    "whisper": settings.tts_whisper_voice_id,  # only the user hears this
    "to_caller": settings.tts_agent_voice_id,  # the agent speaking for the user
}


async def synthesize(kind: str, text: str) -> str | None:
    if not settings.speech_enabled or not settings.elevenlabs_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.speech_timeout_seconds) as client:
            response = await client.post(
                TTS_URL.format(voice_id=VOICES[kind]),
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": settings.elevenlabs_api_key},
                json={"text": text, "model_id": settings.speech_model},
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("Speech generation failed: %s", error)
        return None
    return base64.b64encode(response.content).decode()


async def speech_message(kind: str, text: str) -> dict:
    return {
        "type": "speech",
        "kind": kind,
        "text": text,
        "audio_base64": await synthesize(kind, text),
    }
