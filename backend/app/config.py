from __future__ import annotations
import secrets
from typing import Literal
from urllib.parse import urlsplit
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: Literal["development", "production"] = "development"
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

    @model_validator(mode="after")
    def validate_production(self):
        if self.APP_ENV != "production":
            return self
        if ("AUTH_SECRET" not in self.model_fields_set or len(self.AUTH_SECRET) < 32
                or "replace-with" in self.AUTH_SECRET.lower()):
            raise ValueError("Production requires a stable, private AUTH_SECRET of at least 32 characters")
        if not self.CORS_ORIGINS:
            raise ValueError("Production requires explicit HTTPS CORS_ORIGINS")
        for origin in self.CORS_ORIGINS:
            address = urlsplit(origin)
            if (address.scheme != "https" or not address.hostname or "*" in origin
                    or address.username or address.password or address.path or address.query or address.fragment):
                raise ValueError("Production CORS_ORIGINS must contain exact HTTPS origins without paths")
        media = urlsplit(self.LIVEKIT_URL)
        if media.scheme != "wss" or not media.hostname:
            raise ValueError("Production requires a WSS LIVEKIT_URL")
        if self.LIVEKIT_API_KEY == "devkey" or len(self.LIVEKIT_API_SECRET) < 32:
            raise ValueError("Production requires non-development LiveKit credentials")
        if self.DATABASE_URL.startswith("sqlite") and not self.DATABASE_URL.startswith("sqlite+aiosqlite:////"):
            raise ValueError("Production SQLite requires an absolute path on a persistent volume")
        return self

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()