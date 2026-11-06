import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.services.integrity import CLIENT_TYPES


class InterviewStateOut(BaseModel):
    session_id: uuid.UUID
    device_locked: bool = False
    device_token: str | None = None  # sent once, by the first start
    job_title: str
    status: str
    total_questions: int
    current_index: int
    current_question: str | None
    current_kind: str | None = None
    seconds_per_question: int
    think_seconds: int = 15
    seconds_left: int | None = None
    follow_ups_planned: int = 0
    strikes: int = 0
    max_strikes: int = 3
    terminated: bool = False
    require_webcam: bool = False
    can_answer: bool


class AnswerOut(BaseModel):
    completed: bool
    next_index: int | None = None
    next_question: str | None = None
    next_kind: str | None = None
    total_questions: int
    seconds_left: int | None = None


class IssueIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


class SkipIn(BaseModel):
    question_index: int = Field(ge=0)


ClientEventType = Literal[tuple(sorted(CLIENT_TYPES))]  # type: ignore[valid-type]


class IntegrityEventIn(BaseModel):
    type: ClientEventType
    question_index: int | None = Field(default=None, ge=0, le=50)
    detail: str | None = Field(default=None, max_length=200)
    value: float | None = Field(default=None, ge=0, le=100)


class EventsIn(BaseModel):
    events: list[IntegrityEventIn] = Field(min_length=1, max_length=20)


class EventsOut(BaseModel):
    strikes: int
    max_strikes: int
    terminated: bool
