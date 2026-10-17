from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import instructor_token, require_instructor, is_instructor
from app.models.student import Student
from sqlalchemy import select, delete
from fastapi import Header
from app.database import get_db
from app.schemas.session import (
    CreateSessionRequest,
    JoinSessionRequest,
    SessionOut,
    SessionCreatedOut,
    JoinSessionOut,
    StudentOut,
)
from app.services import session_service
from app.services.livekit_service import create_token

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionCreatedOut)
async def create_session(body: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    session = await session_service.create_session(
        db, body.instructor_name, body.instructor_email, body.course_name
    )
    return SessionCreatedOut(session_id=session.session_id, join_code=session.join_code, instructor_token=instructor_token(session.session_id))


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)):
    session = await session_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(
        session_id=session.session_id,
        join_code=session.join_code,
        course_name=session.course_name,
        instructor_name=session.instructor.name,
        started_at=session.started_at,
        ended_at=session.ended_at,
        students=[
            StudentOut(
                student_id=s.student_id,
                display_name=s.display_name,
                joined_at=s.joined_at,
            )
            for s in session.students if is_instructor(session_id, (authorization or "").removeprefix("Bearer "))
        ],
    )


@router.get("/sessions/code/{join_code}", response_model=SessionOut)
async def get_session_by_code(join_code: str, db: AsyncSession = Depends(get_db)):
    session = await session_service.get_session_by_code(db, join_code.upper())
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(
        session_id=session.session_id,
        join_code=session.join_code,
        course_name=session.course_name,
        instructor_name=session.instructor.name,
        started_at=session.started_at,
        ended_at=session.ended_at,
        students=[],
    )


@router.post("/sessions/{session_id}/join", response_model=JoinSessionOut)
async def join_session(
    session_id: str, body: JoinSessionRequest, db: AsyncSession = Depends(get_db)
):
    session = await session_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.ended_at:
        raise HTTPException(status_code=400, detail="Session has ended")
    student = await session_service.join_session(
        db, session_id, body.display_name, body.device_token, body.consent_version
    )
    return JoinSessionOut(
        student_id=student.student_id,
        device_token=student.device_token,
        session_id=session_id,
    )


@router.post("/sessions/{session_id}/end", dependencies=[Depends(require_instructor)])
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await session_service.end_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    from app.websockets.manager import manager
    await manager.close_session(session_id)
    return {"status": "ended", "ended_at": session.ended_at}


@router.post("/sessions/{session_id}/rtc-token")
async def get_rtc_token(
    session_id: str,
    identity: str = Query(...),
    instructor: bool = Query(False),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.get_session(db, session_id)
    if not session or session.ended_at:
        raise HTTPException(400, "Session is unavailable")
    credential = (authorization or "").removeprefix("Bearer ")
    if instructor:
        if not is_instructor(session_id, credential):
            raise HTTPException(403, "Instructor access required")
    else:
        result = await db.execute(select(Student).where(Student.session_id == session_id, Student.student_id == identity, Student.device_token == credential))
        if not result.scalar_one_or_none():
            raise HTTPException(403, "Student access required")
    token = create_token(session_id, identity, is_instructor=instructor)
    return {"token": token}


@router.post("/sessions/{session_id}/students/{student_id}/withdraw")
async def withdraw_student(session_id: str, student_id: str, authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)):
    from app.models.alert import Alert
    from app.models.attentiveness_reading import AttentivenessReading
    from app.websockets.manager import manager
    from app.services.alert_engine import alert_engine
    credential = (authorization or "").removeprefix("Bearer ")
    student = await db.scalar(select(Student).where(Student.session_id == session_id, Student.student_id == student_id, Student.device_token == credential))
    if not student:
        raise HTTPException(403, "Student access required")
    socket = manager.student_connections.get(session_id, {}).get(student_id)
    if socket:
        await socket.close(code=1000, reason="Consent withdrawn")
    await db.execute(delete(Alert).where(Alert.student_id == student_id))
    await db.execute(delete(AttentivenessReading).where(AttentivenessReading.student_id == student_id))
    await db.execute(delete(Student).where(Student.student_id == student_id))
    await db.commit()
    alert_engine.remove_student(student_id)
    return {"status": "withdrawn"}
