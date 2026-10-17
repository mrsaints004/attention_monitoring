import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_instructor
from app.database import get_db
from app.models.attentiveness_reading import AttentivenessReading
from app.models.student import Student

def safe_cell(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


router = APIRouter(dependencies=[Depends(require_instructor)], tags=["export"])


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query("csv"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AttentivenessReading)
        .join(Student)
        .where(Student.session_id == session_id)
        .options(selectinload(AttentivenessReading.student))
        .order_by(AttentivenessReading.timestamp)
    )
    result = await db.execute(stmt)
    readings = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "timestamp", "student_id", "display_name",
        "s_eye", "s_gaze", "s_yawn", "s_affect",
        "attention_index", "quality_flag", "inference_mode",
    ])
    for r in readings:
        writer.writerow([
            r.timestamp.isoformat(), r.student_id, safe_cell(r.student.display_name),
            r.s_eye, r.s_gaze, r.s_yawn, r.s_affect,
            r.attention_index, r.quality_flag.value, r.inference_mode,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"},
    )
