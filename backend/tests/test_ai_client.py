"""Tests for the real (non-mock) AI code path. The OpenAI SDK is replaced by a fake, so no network is used."""

import json
import uuid
from types import SimpleNamespace

import httpx
import openai
import pytest
from sqlalchemy import select

from app.ai import client as ai
from app.ai.schemas import AnswerEvaluation, QuestionSet, ResumeScreenResult
from app.config import settings
from app.models import AIAuditLog, Application
from tests.conftest import STRONG_RESUME, apply, make_pdf


class FakeLLM:
    """Returns the queued outputs in order. An Exception in the queue is raised instead."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self._transcribe))

    def _next(self):
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._next()
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    def _transcribe(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self._next())


@pytest.fixture()
def real_mode(monkeypatch):
    monkeypatch.setattr(settings, "AI_MOCK", False)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")

    def install(outputs):
        fake = FakeLLM(outputs)
        monkeypatch.setattr(ai, "_llm_client", lambda: fake)
        monkeypatch.setattr(ai, "_stt_client", lambda: fake)
        return fake

    return install


def _status_error(cls, code):
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls("error", response=httpx.Response(code, request=req), body=None)


EVAL_JSON = json.dumps({"accuracy": 8, "relevance": 6, "clarity": 4, "score": 9.9, "feedback": "Good."})


def test_chat_json_validates_and_uses_json_mode(real_mode, db):
    fake = real_mode([EVAL_JSON])
    result = ai.chat_json("sys", "user", AnswerEvaluation, db=db, kind="answer_eval")
    assert result.accuracy == 8 and result.feedback == "Good."
    call = fake.calls[0]
    assert call["temperature"] == 0 and call["response_format"] == {"type": "json_object"}
    assert call["model"] == settings.LLM_MODEL
    rows = db.scalars(select(AIAuditLog)).all()
    assert len(rows) == 1 and rows[0].raw_output == EVAL_JSON and rows[0].model == settings.LLM_MODEL


def test_scores_are_clamped(real_mode, db):
    real_mode(
        [
            json.dumps(
                {
                    "skill_score": 55,
                    "experience_score": -3,
                    "education_score": "12",
                    "skills": "Python, SQL",
                    "reasoning": {"skills": "ok"},
                }
            )
        ]
    )
    r = ai.chat_json("s", "u", ResumeScreenResult, db=db, kind="resume_screen")
    assert (r.skill_score, r.experience_score, r.education_score) == (40, 0, 10)
    assert r.skills == ["Python", "SQL"] and "skills: ok" in r.reasoning_text()


def test_retries_on_invalid_json_then_succeeds(real_mode, db):
    fake = real_mode(["not json", "```json\n" + EVAL_JSON + "\n```"])
    assert ai.chat_json("s", "u", AnswerEvaluation, db=db, kind="answer_eval").clarity == 4
    assert len(fake.calls) == 2
    assert len(db.scalars(select(AIAuditLog)).all()) == 2  # every attempt is audited


def test_retries_on_429_and_5xx(real_mode, db):
    fake = real_mode(
        [_status_error(openai.RateLimitError, 429), _status_error(openai.InternalServerError, 503), EVAL_JSON]
    )
    assert ai.chat_json("s", "u", AnswerEvaluation, db=db, kind="answer_eval").accuracy == 8
    assert len(fake.calls) == 3


def test_gives_up_after_three_attempts(real_mode, db):
    fake = real_mode(["{}", "[1]", "nope", EVAL_JSON])
    with pytest.raises(ai.AIServiceError):
        ai.chat_json("s", "u", AnswerEvaluation, db=db, kind="answer_eval")
    assert len(fake.calls) == 3


def test_non_retryable_error_fails_fast(real_mode, db):
    fake = real_mode([_status_error(openai.AuthenticationError, 401), EVAL_JSON])
    with pytest.raises(ai.AIServiceError):
        ai.chat_json("s", "u", AnswerEvaluation, db=db, kind="answer_eval")
    assert len(fake.calls) == 1


def test_extra_check_retries_wrong_question_count(real_mode, db):
    two = json.dumps({"questions": [{"text": "Question one?", "focus": "a"}, {"text": "Question two?"}]})
    three = json.dumps({"questions": [{"text": f"Question {i}?", "focus": "x"} for i in range(3)]})
    fake = real_mode([two, three])

    def check(r):
        if len(r.questions) != 3:
            raise ai.InvalidAIOutput("wrong count")

    assert len(ai.chat_json("s", "u", QuestionSet, db=db, kind="question_gen", extra_check=check).questions) == 3
    assert len(fake.calls) == 2


def test_transcribe_real_path(real_mode, db):
    fake = real_mode(["  hello world  "])
    assert ai.transcribe(b"abc", "a.webm", db=db) == "hello world"
    assert fake.calls[0]["model"] == settings.STT_MODEL
    assert db.scalars(select(AIAuditLog)).one().kind == "transcribe"


def test_screening_ai_failure_marks_manual_review(real_mode, client, candidate, job, db, emails):
    real_mode(["bad", "bad", "bad"])
    app_id = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()["id"]
    a = db.get(Application, uuid.UUID(app_id))
    assert a.stage == "screening_failed" and a.needs_manual_review
    assert a.review_reason.startswith("AI screening failed")
    assert any("Manual review needed" in e["subject"] for e in emails)


def test_full_screen_with_real_path(real_mode, client, recruiter, candidate, job, db):
    screen = json.dumps(
        {
            "skills": ["Python"],
            "matched_skills": ["Python", "FastAPI"],
            "missing_skills": [],
            "years_experience": 3,
            "education": "BSCS",
            "certifications": [],
            "summary": "Good.",
            "skill_score": 36,
            "experience_score": 20,
            "education_score": 10,
            "reasoning": "ok",
        }
    )
    questions = json.dumps({"questions": [{"text": f"Tell me about topic {i}?", "focus": "t"} for i in range(5)]})
    real_mode([screen, questions])
    app_id = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()["id"]
    detail = client.get(f"/api/applications/{app_id}/detail", headers=recruiter).json()
    assert detail["stage"] == "interview_invited"
    assert detail["scores"]["resume_total"] == 66
    assert [q["index"] for q in detail["interview"]["questions"]] == [0, 1, 2, 3, 4]
