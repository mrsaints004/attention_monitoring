from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.attentiveness_reading import QualityFlag


class ReadingIn(BaseModel):
    inference_mode: Literal["geometric", "four_cue"] = "geometric"
    s_eye: float = Field(ge=0, le=1, allow_inf_nan=False)
    s_gaze: float = Field(ge=0, le=1, allow_inf_nan=False)
    s_yawn: float = Field(ge=0, le=1, allow_inf_nan=False)
    s_affect: float = Field(ge=0, le=1, allow_inf_nan=False)
    attention_index: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    quality_flag: QualityFlag = QualityFlag.normal
    boredom: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    confusion: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    timestamp: datetime | None = None

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.quality_flag != QualityFlag.normal:
            self.attention_index = None
            self.boredom = self.confusion = None
        elif self.attention_index is None:
            raise ValueError("Normal readings require an attention index")
        if self.inference_mode == "geometric":
            self.boredom = self.confusion = None
        return self


class ReadingOut(BaseModel):
    boredom: float | None
    confusion: float | None
    inference_mode: str
    reading_id: str
    student_id: str
    timestamp: datetime
    s_eye: float
    s_gaze: float
    s_yawn: float
    s_affect: float
    attention_index: float | None
    quality_flag: str

    model_config = ConfigDict(from_attributes=True)


class AlertOut(BaseModel):
    alert_id: str
    student_id: str
    reading_id: str
    alert_type: str
    triggered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardStudentUpdate(BaseModel):
    boredom: float | None = None
    confusion: float | None = None
    student_id: str
    display_name: str
    attention_index: float | None
    quality_flag: str
    s_eye: float
    s_gaze: float
    s_yawn: float
    s_affect: float


class DashboardUpdate(BaseModel):
    class_average: float | None
    student_count: int
    students: list[DashboardStudentUpdate]
    recent_alerts: list[AlertOut]