"""Pydantic models that the LLM's JSON output must match. Scores are clamped into their valid range."""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _clamp(lo: float, hi: float):
    def inner(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return lo
        return max(lo, min(hi, v))

    return BeforeValidator(inner)


def _str_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [s.strip() for s in v.split(",") if s.strip()]
    return [str(x) for x in v]


StrList = Annotated[list[str], BeforeValidator(_str_list)]


_LEVELS = ("none", "matric", "high_school", "diploma", "bachelors", "masters", "phd")


def _level(v):
    v = str(v or "").strip().lower().replace("'", "").replace(" ", "_")
    aliases = {
        "bachelor": "bachelors",
        "bachelors_degree": "bachelors",
        "master": "masters",
        "doctorate": "phd",
        "intermediate": "high_school",
        "a_levels": "high_school",
        "o_levels": "matric",
        "ssc": "matric",
    }
    v = aliases.get(v, v)
    return v if v in _LEVELS else "none"


def _cgpa(v):
    """A CGPA out of 4.0, or None when the resume does not state one (or states it on another scale)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if 0 < v <= 4 else None


class ResumeScreenResult(BaseModel):
    skills: StrList = Field(default_factory=list)
    matched_skills: StrList = Field(default_factory=list)
    missing_skills: StrList = Field(default_factory=list)
    years_experience: Annotated[float, _clamp(0, 60)] = 0
    education: str = ""
    # highest level the RESUME shows, used to check the candidate's profile claims
    education_level: Annotated[str, BeforeValidator(_level)] = "none"
    cgpa: Annotated[float | None, BeforeValidator(_cgpa)] = None
    certifications: StrList = Field(default_factory=list)
    summary: str = ""
    skill_score: Annotated[float, _clamp(0, 40)]
    experience_score: Annotated[float, _clamp(0, 20)]
    education_score: Annotated[float, _clamp(0, 10)]
    reasoning: str | dict = ""

    def reasoning_text(self) -> str:
        if isinstance(self.reasoning, dict):
            return "\n".join(f"{k}: {v}" for k, v in self.reasoning.items())
        return self.reasoning


class GeneratedQuestion(BaseModel):
    text: str = Field(min_length=5)
    focus: str = ""


class QuestionSet(BaseModel):
    questions: list[GeneratedQuestion]


class FollowUpQuestion(BaseModel):
    text: str = Field(min_length=5, max_length=400)


class AnswerEvaluation(BaseModel):
    accuracy: Annotated[float, _clamp(0, 10)]
    relevance: Annotated[float, _clamp(0, 10)]
    clarity: Annotated[float, _clamp(0, 10)]
    score: Annotated[float, _clamp(0, 10)] = 0
    feedback: str = ""
