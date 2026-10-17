from __future__ import annotations
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AUTH_SECRET: str = secrets.token_urlsafe(48)
    DATABASE_URL: str = "sqlite+aiosqlite:///./attention_monitor.db"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    ALERT_THRESHOLD: int = 40
    ALERT_DURATION_SECONDS: int = 15
    ALERT_COOLDOWN_SECONDS: int = 60
    WS_THROTTLE_PER_SEC: int = 2
    LIVEKIT_URL: str = "ws://localhost:7880"
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = "secret"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()