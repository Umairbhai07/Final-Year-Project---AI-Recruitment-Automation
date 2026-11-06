import uuid
from datetime import date

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import Timestamps, UUIDPk
from app.models.enums import JobStatus


class Job(UUIDPk, Timestamps, Base):
    __tablename__ = "jobs"

    recruiter_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    required_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    min_experience_years: Mapped[int] = mapped_column(Integer, default=0)
    education_level: Mapped[str] = mapped_column(String(20), default="none")
    min_cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)  # out of 4.0; None = no CGPA rule
    # candidates who tried to apply but did not meet the minimum requirements (they were stopped before applying)
    blocked_applications: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.ACTIVE.value, index=True)
    screening_threshold: Mapped[int] = mapped_column(Integer, default=40)
    num_questions: Mapped[int] = mapped_column(Integer, default=6)
    seconds_per_question: Mapped[int] = mapped_column(Integer, default=120)
    think_seconds: Mapped[int] = mapped_column(Integer, default=15)  # silent thinking time before recording starts
    follow_up_questions: Mapped[int] = mapped_column(Integer, default=1)  # live AI follow-ups per interview
    require_webcam: Mapped[bool] = mapped_column(Boolean, default=True)  # face / eye tracking during the interview
    # questions candidates answer when applying: [{id, label, type, required, options, help, min, max}]
    application_form: Mapped[list[dict]] = mapped_column(JSON, default=list)

    recruiter = relationship("User")
    applications: Mapped[list["Application"]] = relationship(  # noqa: F821
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
