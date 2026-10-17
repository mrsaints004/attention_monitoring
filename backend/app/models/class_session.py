import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ClassSession(Base):
    __tablename__ = "class_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    join_code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.instructor_id"))
    course_name: Mapped[str] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    instructor = relationship("Instructor", back_populates="sessions")
    students = relationship("Student", back_populates="session")