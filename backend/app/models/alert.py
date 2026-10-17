import uuid
import enum
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AlertType(str, enum.Enum):
    low_attention = "low_attention"
    face_not_detected = "face_not_detected"
    prolonged_away = "prolonged_away"
    eyes_closed = "eyes_closed"


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reading_id: Mapped[str] = mapped_column(ForeignKey("attentiveness_readings.reading_id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"))
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType))
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reading = relationship("AttentivenessReading", back_populates="alerts")
