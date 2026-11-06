import re
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import EducationLevel

PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-()]{6,19}$")


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


def _url(v: str | None, host: str | None, label: str) -> str | None:
    v = _clean(v)
    if v is None:
        return None
    if not v.lower().startswith(("http://", "https://")):
        v = "https://" + v
    if not re.match(r"^https?://[^\s/$.?#][^\s]*$", v, re.I):
        raise ValueError(f"{label} is not a valid link")
    if host and host not in v.lower():
        raise ValueError(f"{label} must be a {host} link")
    return v[:300]


class ExperienceItem(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    company: str = Field(min_length=1, max_length=100)
    years: float = Field(ge=0, le=50)
    description: str | None = Field(default=None, max_length=500)


class ProfileIn(BaseModel):
    """Every field is optional so the profile can be saved step by step. Completeness is checked separately."""

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    headline: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=80)
    about: str | None = Field(default=None, max_length=2000)
    highest_degree: EducationLevel | None = None
    field_of_study: str | None = Field(default=None, max_length=120)
    institute: str | None = Field(default=None, max_length=160)
    cgpa: float | None = Field(default=None, ge=0, le=4)
    graduation_year: int | None = Field(default=None, ge=1960)
    experience_years: float | None = Field(default=None, ge=0, le=50)
    experience: list[ExperienceItem] | None = Field(default=None, max_length=10)
    skills: list[str] | None = Field(default=None, max_length=30)
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None

    @field_validator("full_name", "headline", "city", "about", "field_of_study", "institute")
    @classmethod
    def strip(cls, v: str | None) -> str | None:
        return _clean(v)

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str | None) -> str | None:
        v = _clean(v)
        if v is not None and not PHONE_RE.match(v):
            raise ValueError("Enter a valid phone number, for example +92 300 1234567")
        return v

    @field_validator("graduation_year")
    @classmethod
    def year_ok(cls, v: int | None) -> int | None:
        if v is not None and v > date.today().year + 6:
            raise ValueError("Graduation year is too far in the future")
        return v

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        seen: dict[str, str] = {}
        for s in v:
            s = s.strip()[:60]
            if s and s.lower() not in seen:
                seen[s.lower()] = s
        return list(seen.values())

    @model_validator(mode="after")
    def links(self) -> "ProfileIn":
        # only touch links that were sent: assigning a field marks it as "set" and would clear it on save
        for name, host, label in (
            ("linkedin_url", "linkedin.com", "LinkedIn"),
            ("github_url", "github.com", "GitHub"),
            ("portfolio_url", None, "Portfolio"),
        ):
            if name in self.model_fields_set:
                setattr(self, name, _url(getattr(self, name), host, label))
        return self


class Check(BaseModel):
    rule: str
    label: str
    required: str
    yours: str
    ok: bool


class Eligibility(BaseModel):
    eligible: bool
    profile_complete: bool
    checks: list[Check]


class ProfileOut(BaseModel):
    user_id: str
    full_name: str
    email: str
    headline: str | None = None
    phone: str | None = None
    city: str | None = None
    about: str | None = None
    photo_url: str | None = None
    highest_degree: EducationLevel | None = None
    highest_degree_label: str | None = None
    field_of_study: str | None = None
    institute: str | None = None
    cgpa: float | None = None
    graduation_year: int | None = None
    experience_years: float | None = None
    experience: list[ExperienceItem] = []
    skills: list[str] = []
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    resume_filename: str | None = None
    has_resume: bool = False
    completion: int = 0
    missing: list[str] = []
    complete: bool = False
