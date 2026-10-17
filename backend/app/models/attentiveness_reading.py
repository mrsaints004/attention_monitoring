import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class QualityFlag(str, enum.Enum):
    normal = "normal"
    face_not_detected = "face_not_detected"
    away = "away"
    low_confidence = "low_confidence"
    tab_inactive = "tab_inactive"
    monitoring_paused = "monitoring_paused"


class AttentivenessReading(Base):
    __tablename__ = "attentiveness_readings"

    reading_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"))
    model_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cue_models.model_id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    inference_mode: Mapped[str] = mapped_column(String(16), default="geometric", server_default="geometric")
    s_eye: Mapped[float] = mapped_column(Float)
    s_gaze: Mapped[float] = mapped_column(Float)
    s_yawn: Mapped[float] = mapped_column(Float)
    s_affect: Mapped[float] = mapped_column(Float)
    attention_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_flag: Mapped[QualityFlag] = mapped_column(Enum(QualityFlag), default=QualityFlag.normal)

    student = relationship("Student", back_populates="readings")
    cue_model = relationship("CueModel", back_populates="readings")
    alerts = relationship("Alert", back_populates="reading")