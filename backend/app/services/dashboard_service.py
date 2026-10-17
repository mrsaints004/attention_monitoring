from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.models.student import Student
from app.models.alert import Alert
from app.models.attentiveness_reading import AttentivenessReading, QualityFlag


async def dashboard_snapshot(db, session_id):
    # One ranked query for all latest readings rather than one query per student.
    ranked = select(
        AttentivenessReading.reading_id.label("id"),
        func.row_number().over(partition_by=AttentivenessReading.student_id,
                               order_by=AttentivenessReading.timestamp.desc()).label("rank"),
    ).join(Student).where(Student.session_id == session_id).subquery()
    latest = (await db.execute(select(AttentivenessReading).join(
        ranked, ranked.c.id == AttentivenessReading.reading_id).where(ranked.c.rank == 1))).scalars().all()
    by_student = {r.student_id: r for r in latest}
    students = (await db.execute(select(Student).where(Student.session_id == session_id))).scalars().all()
    updates, scores = [], []
    for student in students:
        reading = by_student.get(student.student_id)
        fresh = reading and reading.timestamp >= datetime.utcnow() - timedelta(seconds=5)
        flag = reading.quality_flag.value if fresh else "monitoring_paused"
        score = reading.attention_index if fresh and flag == "normal" else None
        if score is not None:
            scores.append(score)
        updates.append(dict(student_id=student.student_id, display_name=student.display_name,
                            attention_index=score, quality_flag=flag, inference_mode=reading.inference_mode if reading else "geometric",
                            **{cue: getattr(reading, cue) if fresh else 0 for cue in ("s_eye", "s_gaze", "s_yawn", "s_affect")}))
    alerts = (await db.execute(select(Alert).join(Student, Alert.student_id == Student.student_id)
                              .where(Student.session_id == session_id).order_by(Alert.triggered_at.desc()).limit(100))).scalars().all()
    return dict(type="dashboard_update", class_average=round(sum(scores) / len(scores), 1) if scores else None,
                student_count=len(students), students=updates,
                recent_alerts=[dict(alert_id=a.alert_id, student_id=a.student_id, reading_id=a.reading_id,
                                    alert_type=a.alert_type.value, triggered_at=a.triggered_at.isoformat() + "Z") for a in alerts])
