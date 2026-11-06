import uuid

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import Timestamps, UUIDPk


class CandidateProfile(UUIDPk, Timestamps, Base):
    """A candidate's reusable profile. It must be complete before they can apply to any job."""

    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    headline: Mapped[str | None] = mapped_column(String(120), nullable=True)  # e.g. "Junior Python developer"
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    highest_degree: Mapped[str | None] = mapped_column(String(20), nullable=True)  # EducationLevel value
    field_of_study: Mapped[str | None] = mapped_column(String(120), nullable=True)
    institute: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)  # out of 4.0
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    # past roles: [{title, company, years, description}]
    experience: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    linkedin_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    resume_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("User", back_populates="profile")
