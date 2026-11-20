from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
import pytest
from sqlalchemy.exc import OperationalError


@pytest.mark.asyncio
async def test_ready_checks_migrated_database(client):
    response = await client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_unavailable_database_is_not_ready(client, monkeypatch):
    import app.main as main
    @asynccontextmanager
    async def broken_session():
        db = AsyncMock()
        db.execute.side_effect = OperationalError("SELECT", {}, Exception("private connection details"))
        yield db
    monkeypatch.setattr(main, "async_session", broken_session)
    response = await client.get("/api/ready")
    assert response.status_code == 503
    assert "private connection details" not in response.text
    assert (await client.get("/api/health")).status_code == 200
