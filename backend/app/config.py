"""
backend settings live here. Any field can be overridden by an environment 
variable of the same name.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Server
    host: str = "127.0.0.1"
    port: int = 8100
    reload: bool = True  # restart on code changes; turn off when deployed

    # Browser origins allowed to call the API, comma-separated
    cors_origins: str = "http://localhost:3100,http://127.0.0.1:3100"

    # Call audio generation (only needed by tools/generate_audio.py)
    elevenlabs_api_key: str = ""
    tts_model: str = "eleven_multilingual_v2"
    tts_caller_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # George
    tts_user_voice_id: str = "Xb7hH8MSUJpSbSDYk0k2"  # Alice
    tts_default_gap_ms: int = 350  # silence between turns unless a turn sets gap_ms

    # Call audio format
    audio_sample_rate: int = 16000
    audio_channels: int = 2  # left = caller, right = user

    # How often the backend reports how much call audio it has received
    audio_progress_interval_seconds: float = 1.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
