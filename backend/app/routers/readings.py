from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_instructor
from app.database import get_db
from app.models.attentiveness_reading import AttentivenessReading
from app.schemas.reading import ReadingOut

router = APIRouter(dependencies=[Depends(require_instructor)], tags=["readings"])


@router.get("/sessions/{session_id}/readings", response_model=list[ReadingOut])
async def get_readings(
    session_id: str,
    student_id: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    from app.models.student import Student

    stmt = (
        select(AttentivenessReading)
        .join(Student)
        .where(Student.session_id == session_id)
        .order_by(AttentivenessReading.timestamp.desc(), AttentivenessReading.reading_id.desc())
        .limit(limit).offset(offset)
    )
    if student_id:
        stmt = stmt.where(AttentivenessReading.student_id == student_id)
    result = await db.execute(stmt)
    return result.scalars().all()