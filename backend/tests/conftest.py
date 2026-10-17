import asyncio
import os

# Set before importing the app: tests must never create/drop application tables.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["LIVEKIT_API_SECRET"] = "test-only-secret-at-least-thirty-two-characters"
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import engine, Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
