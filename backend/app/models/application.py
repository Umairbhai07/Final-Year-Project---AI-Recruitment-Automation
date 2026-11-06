import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import Timestamps, UUIDPk, utcnow
from app.models.enums import Decision, SessionStatus, Stage


class Application(UUIDPk, Timestamps, Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),)

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(30), default=Stage.SUBMITTED.value, index=True)
    recruiter_decision: Mapped[str] = mapped_column(String(20), default=Decision.PENDING.value)
    recruiter_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # snapshot of the form answers at the time of applying: [{id, label, answer}]
    form_answers: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    # copy of the candidate's profile when they applied (degree, CGPA, experience, links...)
    profile_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # differences the AI found between the profile and the resume: ["Profile says Bachelor's, resume shows Diploma"]
    mismatches: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    recruiter_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="applications")
    candidate = relationship("User")
    resume: Mapped["Resume | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    evaluation: Mapped["EvaluationScore | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    interview: Mapped["InterviewSession | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )


class Resume(UUIDPk, Timestamps, Base):
    __tablename__ = "resumes"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), unique=True
    )
    file_key: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # sha256 of the PDF
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parse_ok: Mapped[bool] = mapped_column(Boolean, default=False)

    application: Mapped[Application] = relationship(back_populates="resume")


class EvaluationScore(UUIDPk, Timestamps, Base):
    __tablename__ = "evaluation_scores"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), unique=True
    )
    skill_score: Mapped[float] = mapped_column(Float, default=0)
    experience_score: Mapped[float] = mapped_column(Float, default=0)
    education_score: Mapped[float] = mapped_column(Float, default=0)
    resume_total: Mapped[float] = mapped_column(Float, default=0)
    interview_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_score: Mapped[float] = mapped_column(Float, default=0)
    resume_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    incomplete: Mapped[bool] = mapped_column(Boolean, default=True)

    application: Mapped[Application] = relationship(back_populates="evaluation")


class InterviewSession(UUIDPk, Timestamps, Base):
    __tablename__ = "interview_sessions"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.INVITED.value)
    questions: Mapped[list[dict]] = mapped_column(JSON, default=list)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issue_reported: Mapped[bool] = mapped_column(Boolean, default=False)
    issue_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # lockdown log: [{type, at, question_index, detail}] written by the browser and by the server
    integrity_events: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    question_served_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated: Mapped[bool] = mapped_column(Boolean, default=False)
    terminated_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # webcam snapshots: [{index, key, at, reason, question_index}]
    snapshots: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    # the interview is locked to the browser that started it (hash of a secret only that browser has)
    device_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    application: Mapped[Application] = relationship(back_populates="interview")
    responses: Mapped[list["InterviewResponse"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewResponse.question_index"
    )


class InterviewResponse(UUIDPk, Timestamps, Base):
    __tablename__ = "interview_responses"
    __table_args__ = (UniqueConstraint("session_id", "question_index", name="uq_response_session_question"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    question_index: Mapped[int] = mapped_column(Integer)
    audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0)
    relevance: Mapped[float] = mapped_column(Float, default=0)
    clarity: Mapped[float] = mapped_column(Float, default=0)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    # the AI was busy or down when the answer arrived: the audio is saved and it is scored later
    pending: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[InterviewSession] = relationship(back_populates="responses")


class AIAuditLog(UUIDPk, Base):
    """Insert-only log of every AI call. Never updated or deleted (DB trigger enforces it)."""

    __tablename__ = "ai_audit_log"

    application_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    input: Mapped[str] = mapped_column(Text)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
