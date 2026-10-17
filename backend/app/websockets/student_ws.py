import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.attentiveness_reading import AttentivenessReading
from app.models.class_session import ClassSession
from app.models.student import Student
from app.schemas.reading import ReadingIn
from app.websockets.manager import manager
from app.services.alert_engine import alert_engine

router = APIRouter()


def socket_credential(websocket):
    protocols = websocket.headers.get("sec-websocket-protocol", "").split(",")
    return protocols[1].strip() if len(protocols) == 2 and protocols[0].strip() == "attention" else None


def valid_origin(websocket):
    origin = websocket.headers.get("origin")
    return not origin or origin in settings.CORS_ORIGINS


@router.websocket("/ws/student/{session_id}/{student_id}")
async def student_websocket(websocket: WebSocket, session_id: str, student_id: str):
    async with async_session() as db:
        student = await db.scalar(select(Student).where(Student.session_id == session_id,
                                  Student.student_id == student_id, Student.device_token == socket_credential(websocket)))
        session = await db.get(ClassSession, session_id)
        if not valid_origin(websocket) or not student or student.consent_version != "v1" or not session or session.ended_at:
            await websocket.close(code=1008)
            return
    await manager.connect_student(session_id, student_id, websocket)
    try:
        while True:
            try:
                data = await websocket.receive_json()
                raw = data if isinstance(data, list) else [data]
                if not 1 <= len(raw) <= 100:
                    raise ValueError("Send 1 to 100 readings per batch")
                readings = [ReadingIn.model_validate(item) for item in raw]
            except (ValidationError, ValueError, json.JSONDecodeError):
                await websocket.send_json({"type": "error", "detail": "Invalid reading batch"})
                continue
            async with async_session() as db:
                session = await db.get(ClassSession, session_id)
                if not session or session.ended_at or not await db.get(Student, student_id):
                    await websocket.close(code=1000, reason="Session ended")
                    return
                for data in readings:
                    now = datetime.utcnow()
                    timestamp = data.timestamp
                    if timestamp and timestamp.tzinfo:
                        timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
                    timestamp = timestamp or now
                    age = (now - timestamp).total_seconds()
                    if age < -5 or age > 60:
                        continue
                    reading = AttentivenessReading(reading_id=str(uuid.uuid4()), student_id=student_id,
                        timestamp=timestamp, s_eye=data.s_eye, s_gaze=data.s_gaze,
                        s_yawn=data.s_yawn, s_affect=data.s_affect,
                        attention_index=data.attention_index, quality_flag=data.quality_flag, inference_mode=data.inference_mode)
                    db.add(reading)
                    await db.flush()
                    # Old buffered data is historical evidence, not a live alert episode.
                    if age <= 3:
                        await alert_engine.process_reading(db, student_id, reading.reading_id,
                            reading.attention_index, reading.quality_flag.value, reading.s_eye)
                    else:
                        alert_engine.remove_student(student_id)
                await db.commit()
    except WebSocketDisconnect:
        pass
    finally:
        current = manager.student_connections.get(session_id, {}).get(student_id)
        if current is websocket:
            manager.disconnect_student(session_id, student_id)
            alert_engine.remove_student(student_id)
