"""The short application form a recruiter attaches to a job (experience, degree, CGPA, ...)."""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

QuestionType = Literal["text", "long_text", "number", "select", "yes_no", "url"]
MAX_QUESTIONS = 15
YES_NO = {"Yes", "No"}


class FormQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=2, max_length=200)
    type: QuestionType = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=20)
    help: str | None = Field(default=None, max_length=200)
    min: float | None = None
    max: float | None = None
    # Must-have rules. An answer outside them is accepted, but the application is marked "not qualified" at once
    # and the candidate is told why. accept: the answers that pass (Yes / No or dropdown). must_min / must_max:
    # the range that passes for a number (e.g. expected salary at most 150000).
    accept: list[str] = Field(default_factory=list, max_length=20)
    must_min: float | None = None
    must_max: float | None = None

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str) -> str:
        return v.strip()

    @field_validator("options")
    @classmethod
    def clean_options(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for o in v:
            o = o.strip()[:100]
            if o and o not in out:
                out.append(o)
        return out

    @model_validator(mode="after")
    def check_select(self) -> "FormQuestion":
        if self.type == "select" and len(self.options) < 2:
            raise ValueError(f"'{self.label}' needs at least two options")
        if self.type != "select":
            self.options = []
        allowed = self.options if self.type == "select" else sorted(YES_NO) if self.type == "yes_no" else []
        self.accept = [a for a in dict.fromkeys(a.strip() for a in self.accept) if a]
        if self.accept and not allowed:
            raise ValueError(f"'{self.label}': only Yes / No and dropdown questions can have must-have answers")
        if any(a not in allowed for a in self.accept):
            raise ValueError(f"'{self.label}': a must-have answer is not one of the options")
        if self.type != "number":
            self.must_min = self.must_max = None
        if self.must_min is not None and self.must_max is not None and self.must_min > self.must_max:
            raise ValueError(f"'{self.label}': the lowest passing value is above the highest")
        if self.accept or self.must_min is not None or self.must_max is not None:
            self.required = True  # a must-have question has to be answered
        return self


def validate_form(questions: list[FormQuestion]) -> list[FormQuestion]:
    if len(questions) > MAX_QUESTIONS:
        raise ValueError(f"A job can have at most {MAX_QUESTIONS} form questions")
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Form questions must have unique ids")
    return questions


# Degree, CGPA and experience now come from the candidate's profile (and are checked against the job's minimum
# requirements), so a new job starts with no extra questions. Recruiters can add their own.
DEFAULT_FORM: list[dict] = []

URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.I)


def check_answers(questions: list[dict], raw: dict) -> list[dict]:
    """Validate a candidate's answers against the job's form. Returns a snapshot [{id, label, answer}].

    Raises ValueError with a message naming the question, so the candidate knows what to fix.
    """
    out: list[dict] = []
    for q in questions:
        value = raw.get(q["id"])
        text = "" if value is None else str(value).strip()
        if not text:
            if q.get("required"):
                raise ValueError(f"Please answer: {q['label']}")
            continue
        kind = q.get("type", "text")
        limit = 3000 if kind == "long_text" else 300
        if len(text) > limit:
            raise ValueError(f"'{q['label']}' is too long (max {limit} characters)")
        if kind == "number":
            try:
                num = float(text)
            except ValueError:
                raise ValueError(f"'{q['label']}' must be a number") from None
            lo, hi = q.get("min"), q.get("max")
            if (lo is not None and num < lo) or (hi is not None and num > hi):
                rng = (
                    f"between {lo:g} and {hi:g}"
                    if lo is not None and hi is not None
                    else (f"at least {lo:g}" if lo is not None else f"at most {hi:g}")
                )
                raise ValueError(f"'{q['label']}' must be {rng}")
            text = f"{num:g}"
        elif kind == "select" and text not in q.get("options", []):
            raise ValueError(f"Choose one of the options for '{q['label']}'")
        elif kind == "yes_no" and text not in YES_NO:
            raise ValueError(f"Answer Yes or No for '{q['label']}'")
        elif kind == "url" and not URL_RE.match(text):
            raise ValueError(f"'{q['label']}' must be a link starting with http:// or https://")
        out.append({"id": q["id"], "label": q["label"], "answer": text})
    return out


def must_have_failures(questions: list[dict], answers: list[dict]) -> list[str]:
    """Plain sentences for every must-have rule the answers miss, e.g. "Can you work on-site?: needs Yes"."""
    given = {a["id"]: a["answer"] for a in answers}
    out = []
    for q in questions:
        answer = given.get(q["id"])
        if answer is None:
            continue
        accept, lo, hi = q.get("accept") or [], q.get("must_min"), q.get("must_max")
        if accept and answer not in accept:
            out.append(f"{q['label']}: needs {' or '.join(accept)}, you answered {answer}")
        elif lo is not None or hi is not None:
            num = float(answer)
            if lo is not None and num < lo:
                out.append(f"{q['label']}: needs at least {lo:g}, you answered {answer}")
            elif hi is not None and num > hi:
                out.append(f"{q['label']}: needs at most {hi:g}, you answered {answer}")
    return out
