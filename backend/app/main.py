from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
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
