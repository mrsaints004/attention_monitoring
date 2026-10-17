import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.auth import is_instructor
from app.database import async_session
from app.models.class_session import ClassSession
from app.services.dashboard_service import dashboard_snapshot
from app.websockets.manager import manager
from app.websockets.student_ws import socket_credential, valid_origin

router = APIRouter()


@router.websocket("/ws/instructor/{session_id}")
async def instructor_websocket(websocket: WebSocket, session_id: str):
    if not valid_origin(websocket) or not is_instructor(session_id, socket_credential(websocket)):
        await websocket.close(code=1008)
        return
    async with async_session() as db:
        if not await db.get(ClassSession, session_id):
            await websocket.close(code=1008)
            return
    await manager.connect_instructor(session_id, websocket)
    try:
        while True:
            async with async_session() as db:
                await websocket.send_json(await dashboard_snapshot(db, session_id))
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1)
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_instructor(session_id, websocket)
