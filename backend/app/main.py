from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, async_session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.routers import sessions, readings, export
from app.websockets.student_ws import router as student_ws_router
from app.websockets.instructor_ws import router as instructor_ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Attention Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api")
app.include_router(readings.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(student_ws_router)
app.include_router(instructor_ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/ready")
async def ready():
    """Readiness includes database access; liveness remains independent of storage."""
    try:
        async with async_session() as db:
            await db.execute(text("SELECT session_id FROM class_sessions LIMIT 1"))
            await db.execute(text("SELECT boredom, confusion FROM attentiveness_readings LIMIT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database is unavailable or migrations are incomplete")
    return {"status": "ready"}
