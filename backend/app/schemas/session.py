from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class RequestModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class CreateSessionRequest(RequestModel):
    instructor_name: str = Field(min_length=1, max_length=255)
    instructor_email: str = Field(min_length=1, max_length=255)
    course_name: str = Field(min_length=1, max_length=255)


class JoinSessionRequest(RequestModel):
    consent_version: Literal["v1"]
    display_name: str = Field(min_length=1, max_length=255)
    device_token: str | None = None


class StudentOut(BaseModel):
    student_id: str
    display_name: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionOut(BaseModel):
    session_id: str
    join_code: str
    course_name: str
    instructor_name: str
    started_at: datetime
    ended_at: datetime | None
    students: list[StudentOut]

    model_config = ConfigDict(from_attributes=True)


class SessionCreatedOut(BaseModel):
    session_id: str
    join_code: str
    instructor_token: str


class JoinSessionOut(BaseModel):
    student_id: str
    device_token: str
    session_id: str