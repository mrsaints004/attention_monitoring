from __future__ import annotations
import time
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.alert import Alert, AlertType
from app.models.attentiveness_reading import QualityFlag


class StudentAlertState:
    def __init__(self):
        self.low_attention_since: float | None = None
        self.face_missing_since: float | None = None
        self.eyes_closed_since: float | None = None
        self.last_alert_time: float = 0


class AlertEngine:
    def __init__(self):
        self.states: dict[str, StudentAlertState] = {}

    def _get_state(self, student_id: str) -> StudentAlertState:
        if student_id not in self.states:
            self.states[student_id] = StudentAlertState()
        return self.states[student_id]

    async def process_reading(
        self,
        db: AsyncSession,
        student_id: str,
        reading_id: str,
        attention_index: float | None,
        quality_flag: str,
        s_eye: float,
    ) -> list[Alert]:
        state = self._get_state(student_id)
        now = time.time()
        alerts: list[Alert] = []

        # Missing or unreliable evidence must not count as disengagement.
        # Reset timers even during cooldown so separate episodes cannot accumulate.
        if attention_index is None and quality_flag == QualityFlag.normal.value:
            state.low_attention_since = None
            state.eyes_closed_since = None
            return alerts

        if quality_flag != QualityFlag.normal.value:
            state.low_attention_since = None
            state.eyes_closed_since = None
            if quality_flag != QualityFlag.face_not_detected.value:
                state.face_missing_since = None
                return alerts
        else:
            state.face_missing_since = None
            if attention_index >= settings.ALERT_THRESHOLD:
                state.low_attention_since = None
            if s_eye >= 0.1:
                state.eyes_closed_since = None

        if now - state.last_alert_time < settings.ALERT_COOLDOWN_SECONDS:
            return alerts

        # Low attention alert
        if quality_flag == QualityFlag.normal.value and attention_index < settings.ALERT_THRESHOLD:
            if state.low_attention_since is None:
                state.low_attention_since = now
            elif now - state.low_attention_since >= settings.ALERT_DURATION_SECONDS:
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    reading_id=reading_id,
                    student_id=student_id,
                    alert_type=AlertType.low_attention,
                    triggered_at=datetime.utcnow(),
                )
                db.add(alert)
                alerts.append(alert)
                state.last_alert_time = now
                state.low_attention_since = None
        else:
            state.low_attention_since = None

        # Face not detected
        if quality_flag == QualityFlag.face_not_detected.value:
            if state.face_missing_since is None:
                state.face_missing_since = now
            elif now - state.face_missing_since >= settings.ALERT_DURATION_SECONDS:
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    reading_id=reading_id,
                    student_id=student_id,
                    alert_type=AlertType.face_not_detected,
                    triggered_at=datetime.utcnow(),
                )
                db.add(alert)
                alerts.append(alert)
                state.last_alert_time = now
                state.face_missing_since = None
        else:
            state.face_missing_since = None

        # Eyes closed prolonged
        if quality_flag == QualityFlag.normal.value and s_eye < 0.1:
            if state.eyes_closed_since is None:
                state.eyes_closed_since = now
            elif now - state.eyes_closed_since >= 3:
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    reading_id=reading_id,
                    student_id=student_id,
                    alert_type=AlertType.eyes_closed,
                    triggered_at=datetime.utcnow(),
                )
                db.add(alert)
                alerts.append(alert)
                state.last_alert_time = now
                state.eyes_closed_since = None
        else:
            state.eyes_closed_since = None

        if alerts:
            await db.commit()
        return alerts

    def remove_student(self, student_id: str):
        self.states.pop(student_id, None)


alert_engine = AlertEngine()