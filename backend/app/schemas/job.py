import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EducationLevel, JobStatus
from app.schemas.form import DEFAULT_FORM, FormQuestion, validate_form


class JobBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=20000)
    required_skills: list[str] = Field(min_length=1, max_length=30)
    min_experience_years: int = Field(default=0, ge=0, le=40)
    education_level: EducationLevel = EducationLevel.NONE
    min_cgpa: float | None = Field(default=None, ge=0, le=4)
    deadline: date | None = None
    screening_threshold: int = Field(default=40, ge=0, le=70)
    num_questions: int = Field(default=6, ge=5, le=8)
    seconds_per_question: int = Field(default=120, ge=30, le=600)
    think_seconds: int = Field(default=15, ge=5, le=60)
    follow_up_questions: int = Field(default=1, ge=0, le=3)
    require_webcam: bool = True
    application_form: list[FormQuestion] = Field(default_factory=lambda: [FormQuestion(**q) for q in DEFAULT_FORM])

    @field_validator("min_cgpa")
    @classmethod
    def zero_is_none(cls, v: float | None) -> float | None:
        return v or None

    @field_validator("application_form")
    @classmethod
    def check_form(cls, v: list[FormQuestion]) -> list[FormQuestion]:
        return validate_form(v)

    @field_validator("required_skills")
    @classmethod
    def clean_skills(cls, v: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for s in v:
            s = s.strip()
            if s and s.lower() not in seen:
                seen[s.lower()] = s[:60]
        if not seen:
            raise ValueError("At least one required skill is needed")
        return list(seen.values())


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=20, max_length=20000)
    required_skills: list[str] | None = Field(default=None, min_length=1, max_length=30)
    min_experience_years: int | None = Field(default=None, ge=0, le=40)
    education_level: EducationLevel | None = None
    min_cgpa: float | None = Field(default=None, ge=0, le=4)
    deadline: date | None = None
    screening_threshold: int | None = Field(default=None, ge=0, le=70)
    num_questions: int | None = Field(default=None, ge=5, le=8)
    seconds_per_question: int | None = Field(default=None, ge=30, le=600)
    think_seconds: int | None = Field(default=None, ge=5, le=60)
    follow_up_questions: int | None = Field(default=None, ge=0, le=3)
    require_webcam: bool | None = None
    application_form: list[FormQuestion] | None = None

    @field_validator("application_form")
    @classmethod
    def check_form(cls, v: list[FormQuestion] | None) -> list[FormQuestion] | None:
        return None if v is None else validate_form(v)

    @field_validator("required_skills")
    @classmethod
    def clean_skills(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else JobBase.clean_skills(v)


class JobStatusIn(BaseModel):
    status: JobStatus


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    description: str
    required_skills: list[str]
    min_experience_years: int
    education_level: EducationLevel
    min_cgpa: float | None = None
    deadline: date | None
    status: JobStatus
    screening_threshold: int
    num_questions: int
    seconds_per_question: int
    think_seconds: int = 15
    follow_up_questions: int = 1
    require_webcam: bool = True
    application_form: list[FormQuestion] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    company: str | None = None
    has_applied: bool | None = None
    eligibility: dict | None = None  # candidates only: does their profile meet the minimum requirements?
    blocked_applications: int | None = None  # recruiters only


class JobMineOut(JobOut):
    applicant_count: int = 0
    evaluated_count: int = 0
    avg_score: float | None = None
