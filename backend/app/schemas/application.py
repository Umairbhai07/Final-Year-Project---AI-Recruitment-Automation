import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import Decision, Stage


class ApplicationCreatedOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    stage: Stage
    created_at: datetime
    status_label: str = "Submitted"
    reason: str | None = None  # why it was not selected, when screening has already finished


class MyApplicationOut(BaseModel):
    """What a CANDIDATE sees about their own application. No scores, never the word 'rejected'."""

    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    job_status: str
    status_label: str
    stage_step: int
    applied_at: datetime
    updated_at: datetime
    interview_session_id: uuid.UUID | None = None
    interview_status: str | None = None
    can_start_interview: bool = False
    shortlisted: bool = False
    reason: str | None = None  # why it was not selected (no scores)


class DecisionIn(BaseModel):
    decision: Decision
    notes: str | None = Field(default=None, max_length=5000)


class CandidateRow(BaseModel):
    rank: int
    application_id: uuid.UUID
    candidate_id: uuid.UUID
    full_name: str
    email: str
    photo_url: str | None = None
    headline: str | None = None
    city: str | None = None
    degree: str | None = None
    experience_years: float | None = None
    cgpa: float | None = None
    mismatch_count: int = 0
    stage: Stage
    decision: Decision
    composite_score: float | None
    skill_score: float | None
    experience_score: float | None
    education_score: float | None
    resume_total: float | None
    interview_score: float | None
    incomplete: bool
    needs_manual_review: bool
    issue_reported: bool
    integrity_level: str | None = None
    interview_completed_at: datetime | None = None
    last_activity_at: datetime | None = None
    last_activity: str | None = None
    is_new: bool = False
    archived: bool
    form_answers: list[dict] = []
    applied_at: datetime


class ResponseOut(BaseModel):
    question_index: int
    question: str
    focus: str
    transcript: str | None
    accuracy: float
    relevance: float
    clarity: float
    score: float
    feedback: str | None
    has_audio: bool
    kind: str = "main"
    pending: bool = False


class InterviewDetailOut(BaseModel):
    session_id: uuid.UUID
    status: str
    total_questions: int
    current_index: int
    invited_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    issue_reported: bool
    issue_text: str | None
    questions: list[dict]
    responses: list[ResponseOut]
    integrity: dict | None = None
    device_locked: bool = False


class ScoresOut(BaseModel):
    skill_score: float
    experience_score: float
    education_score: float
    resume_total: float
    interview_score: float | None
    composite_score: float
    resume_reasoning: str | None
    incomplete: bool


class ApplicationDetailOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    required_skills: list[str]
    candidate: dict
    profile_snapshot: dict | None = None
    mismatches: list[str] = []
    requirements: list[dict] = []
    stage: Stage
    decision: Decision
    notes: str | None
    needs_manual_review: bool
    review_reason: str | None
    archived: bool
    applied_at: datetime
    resume_filename: str | None
    form_answers: list[dict] = []
    parsed_resume: dict | None
    scores: ScoresOut | None
    interview: InterviewDetailOut | None


class JobStatsOut(BaseModel):
    job_id: uuid.UUID
    total: int
    by_stage: dict[str, int]
    by_decision: dict[str, int]
    screened: int
    interviewed: int
    evaluated: int
    avg_composite: float | None
    avg_resume: float | None
    histogram: list[dict]
    funnel: list[dict] = []
    missing_skills: list[dict] = []
    breakdown: list[dict] = []
    integrity: dict = {}
    degrees: list[dict] = []
    blocked_applications: int = 0
    mismatches: int = 0


class OverviewApp(BaseModel):
    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    full_name: str
    stage: Stage
    decision: Decision
    composite_score: float | None
    incomplete: bool
    applied_at: datetime
    reason: str | None = None
    last_activity_at: datetime | None = None
    last_activity: str | None = None
    is_new: bool = False
    integrity_level: str | None = None


class OverviewJob(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    deadline: date | None = None
    required_skills: list[str] = []
    applicants: int
    new: int
    screening: int
    waiting_interview: int
    to_review: int
    needs_attention: int
    shortlisted: int
    avg_score: float | None
    top_score: float | None
    blocked: int
    funnel: list[dict]
    last_activity_at: datetime | None = None


class OverviewOut(BaseModel):
    jobs: list[OverviewJob] = []
    jobs_total: int
    jobs_active: int
    applications_total: int
    interviews_pending: int
    evaluated: int
    shortlisted: int
    needs_attention: int
    avg_composite: float | None
    recent: list[OverviewApp]
    recent_interviews: list[OverviewApp] = []
    new_count: int = 0
    attention: list[OverviewApp]
    awaiting_decision: list[OverviewApp]
