import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("class_sessions.session_id"))
    display_name: Mapped[str] = mapped_column(String(255))
    device_token: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()))
    consent_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    consented_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("ClassSession", back_populates="students")
    readings = relationship("AttentivenessReading", back_populates="student")
