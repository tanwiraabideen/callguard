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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
