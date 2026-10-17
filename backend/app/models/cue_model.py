import uuid
from sqlalchemy import String, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CueModel(Base):
    __tablename__ = "cue_models"

    model_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version: Mapped[str] = mapped_column(String(50))
    fusion_weights: Mapped[dict] = mapped_column(JSON)
    cut_points: Mapped[dict] = mapped_column(JSON)
    accuracy: Mapped[float] = mapped_column(Float)

    readings = relationship("AttentivenessReading", back_populates="cue_model")
