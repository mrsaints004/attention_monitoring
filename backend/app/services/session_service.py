from __future__ import annotations
import secrets
import string
import uuid
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.instructor import Instructor
from app.models.class_session import ClassSession
from app.models.student import Student


def generate_join_code(length: int = 6) -> str:
    return "".join((secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length)))


async def create_session(
    db: AsyncSession, instructor_name: str, instructor_email: str, course_name: str
) -> ClassSession:
    result = await db.execute(
        select(Instructor).where(Instructor.email == instructor_email)
    )
    instructor = result.scalar_one_or_none()
    if not instructor:
        instructor = Instructor(name=instructor_name, email=instructor_email)
        db.add(instructor)
        await db.flush()

    join_code = generate_join_code()
    session = ClassSession(
        instructor_id=instructor.instructor_id,
        course_name=course_name,
        join_code=join_code,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: str) -> ClassSession | None:
    result = await db.execute(
        select(ClassSession)
        .where(ClassSession.session_id == session_id)
        .options(
            selectinload(ClassSession.students),
            selectinload(ClassSession.instructor),
        )
    )
    return result.scalar_one_or_none()


async def get_session_by_code(db: AsyncSession, join_code: str) -> ClassSession | None:
    result = await db.execute(
        select(ClassSession)
        .where(ClassSession.join_code == join_code)
        .options(
            selectinload(ClassSession.students),
            selectinload(ClassSession.instructor),
        )
    )
    return result.scalar_one_or_none()


async def join_session(
    db: AsyncSession, session_id: str, display_name: str, device_token: str | None = None, consent_version: str = "v1"
) -> Student:
    if device_token:
        result = await db.execute(
            select(Student).where(
                Student.session_id == session_id,
                Student.device_token == device_token,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.display_name = display_name
            existing.consent_version = consent_version
            existing.consented_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing)
            return existing

    student = Student(
        session_id=session_id,
        display_name=display_name,
        device_token=str(uuid.uuid4()),
        consent_version=consent_version, consented_at=datetime.utcnow(),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def end_session(db: AsyncSession, session_id: str) -> ClassSession | None:
    session = await get_session(db, session_id)
    if session and not session.ended_at:
        session.ended_at = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
    return session