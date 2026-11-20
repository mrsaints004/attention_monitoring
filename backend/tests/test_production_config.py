import pytest
from pydantic import ValidationError
from app.config import Settings


def production(**overrides):
    values = dict(APP_ENV="production", AUTH_SECRET="a-private-signing-secret-of-at-least-32-characters",
                  CORS_ORIGINS=["https://classroom.example.org"],
                  LIVEKIT_URL="wss://media.example.org", LIVEKIT_API_KEY="production-key",
                  LIVEKIT_API_SECRET="a-private-media-secret-of-at-least-32-characters",
                  DATABASE_URL="sqlite+aiosqlite:////var/data/attention.db")
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_configuration():
    assert production().APP_ENV == "production"


@pytest.mark.parametrize("override", [
    dict(AUTH_SECRET="replace-with-a-long-random-secret"),
    dict(CORS_ORIGINS=["*"]), dict(CORS_ORIGINS=["http://localhost:3000"]),
    dict(CORS_ORIGINS=["https://classroom.example.org/path"]),
    dict(LIVEKIT_URL="ws://localhost:7880"), dict(LIVEKIT_API_KEY="devkey"),
    dict(LIVEKIT_API_SECRET="secret"), dict(DATABASE_URL="sqlite+aiosqlite:///./local.db"),
])
def test_production_rejects_development_configuration(override):
    with pytest.raises(ValidationError):
        production(**override)


def test_production_rejects_generated_signing_key(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    values = production().model_dump()
    values.pop("AUTH_SECRET")
    with pytest.raises(ValidationError, match="stable, private AUTH_SECRET"):
        Settings(_env_file=None, **values)
