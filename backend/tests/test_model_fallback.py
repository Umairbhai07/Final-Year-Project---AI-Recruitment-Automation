"""If Groq retires LLM_MODEL, the client switches to another chat model instead of failing."""

from types import SimpleNamespace

import httpx
import openai

from app.ai import client as ai
from app.config import settings


def _not_found(model: str) -> openai.NotFoundError:
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    msg = f"The model `{model}` does not exist or you do not have access to it."
    return openai.NotFoundError(msg, response=httpx.Response(404, request=req), body=None)


class FakeClient:
    def __init__(self, available):
        self.available = available
        self.tried = []
        self.models = SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id=m) for m in available]))
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, **kwargs):
        self.tried.append(model)
        if model not in self.available:
            raise _not_found(model)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))])


def test_switches_to_available_model(monkeypatch):
    fake = FakeClient(["whisper-large-v3", "openai/gpt-oss-120b", "llama-3.1-8b-instant"])
    monkeypatch.setattr(ai, "_llm_client", lambda: fake)
    monkeypatch.setattr(ai, "_working_model", None)
    monkeypatch.setattr(ai, "_dead_models", set())
    monkeypatch.setattr(settings, "LLM_MODEL", "llama-3.3-70b-versatile")

    ai._chat_completion(messages=[])
    assert fake.tried == ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
    assert ai._working_model == "openai/gpt-oss-120b"

    fake.tried.clear()
    ai._chat_completion(messages=[])
    assert fake.tried == ["openai/gpt-oss-120b"]  # remembered, no extra calls


def test_other_errors_are_not_swallowed(monkeypatch):
    class Boom(FakeClient):
        def _create(self, model, **kwargs):
            raise openai.APIConnectionError(request=httpx.Request("POST", "https://x"))

    monkeypatch.setattr(ai, "_llm_client", lambda: Boom(["llama-3.3-70b-versatile"]))
    monkeypatch.setattr(ai, "_working_model", None)
    monkeypatch.setattr(ai, "_dead_models", set())
    try:
        ai._chat_completion(messages=[])
    except openai.APIConnectionError:
        pass
    else:
        raise AssertionError("connection errors must reach the retry logic")


def _rate_limited(msg: str, headers=None) -> openai.RateLimitError:
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return openai.RateLimitError(msg, response=httpx.Response(429, request=req, headers=headers or {}), body=None)


def test_rate_limit_delay_is_read_from_groq_message():
    assert ai.rate_limit_delay(_rate_limited("Please try again in 3.157s. Need more tokens?")) == 3.157
    assert ai.rate_limit_delay(_rate_limited("Please try again in 285ms.")) == 0.285
    assert ai.rate_limit_delay(_rate_limited("Please try again in 1m2.5s.")) == 60.0  # capped
    assert ai.rate_limit_delay(_rate_limited("x", {"retry-after": "7"})) == 7.0
    assert ai.rate_limit_delay(ValueError("nope")) is None


def test_rate_limit_retries_until_it_clears(monkeypatch, db):
    from pydantic import BaseModel

    class Out(BaseModel):
        ok: bool

    calls = {"n": 0}

    class Limited(FakeClient):
        def _create(self, model, **kwargs):
            calls["n"] += 1
            if calls["n"] < 6:  # more than the normal 3 tries
                raise _rate_limited("Rate limit reached. Please try again in 10ms.")
            return super()._create(model, **kwargs)

    monkeypatch.setattr(ai, "_llm_client", lambda: Limited(["llama-3.3-70b-versatile"]))
    monkeypatch.setattr(ai, "_working_model", None)
    monkeypatch.setattr(ai, "_dead_models", set())
    monkeypatch.setattr(settings, "LLM_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "AI_MOCK", False)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test")
    assert ai.chat_json("s", "u", Out, db=db, kind="test").ok is True
    assert calls["n"] == 6


def test_daily_limit_moves_to_the_next_model_without_waiting(monkeypatch, db):
    """Free-tier tokens-per-day used up: waiting would not help, so the next model (own limits) is used."""
    from pydantic import BaseModel

    class Out(BaseModel):
        ok: bool

    class DailyLimited(FakeClient):
        def _create(self, model, **kwargs):
            if model == "llama-3.3-70b-versatile":
                self.tried.append(model)
                raise _rate_limited("Rate limit reached on tokens per day (TPD). Please try again in 1h12m3.5s.")
            return super()._create(model, **kwargs)

    fake = DailyLimited(["llama-3.3-70b-versatile", "openai/gpt-oss-120b"])
    monkeypatch.setattr(ai, "_llm_client", lambda: fake)
    monkeypatch.setattr(ai, "_working_model", None)
    monkeypatch.setattr(ai, "_dead_models", set())
    monkeypatch.setattr(ai, "_cooling", {})
    monkeypatch.setattr(ai, "_available", None)
    monkeypatch.setattr(settings, "LLM_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "AI_MOCK", False)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test")
    assert ai.rate_limit_delay(_rate_limited("Please try again in 1h12m3.5s."), cap=None) == 4323.5
    assert ai.chat_json("s", "u", Out, db=db, kind="test").ok is True
    assert fake.tried == ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]

    fake.tried.clear()  # the limited model is skipped until its limit ends
    assert ai.chat_json("s", "u", Out, db=db, kind="test").ok is True
    assert fake.tried == ["openai/gpt-oss-120b"]


def test_all_models_limited_fails_fast_with_a_clear_error(monkeypatch, db):
    from pydantic import BaseModel

    class Out(BaseModel):
        ok: bool

    class AllLimited(FakeClient):
        def _create(self, model, **kwargs):
            self.tried.append(model)
            raise _rate_limited("Rate limit reached on requests per day (RPD). Please try again in 20m.0s.")

    fake = AllLimited(["llama-3.3-70b-versatile", "openai/gpt-oss-120b"])
    monkeypatch.setattr(ai, "_llm_client", lambda: fake)
    monkeypatch.setattr(ai, "_working_model", None)
    monkeypatch.setattr(ai, "_dead_models", set())
    monkeypatch.setattr(ai, "_cooling", {})
    monkeypatch.setattr(ai, "_available", None)
    monkeypatch.setattr(settings, "LLM_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "AI_MOCK", False)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test")
    try:
        ai.chat_json("s", "u", Out, db=db, kind="test")
    except ai.AIServiceError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("expected AIServiceError")
    assert fake.tried == ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]  # each tried once, no long waits


def test_whisper_moves_to_turbo_when_its_limit_is_used_up(monkeypatch, db):
    tried = []

    def create(model, **kwargs):
        tried.append(model)
        if model == "whisper-large-v3":
            raise _rate_limited("Rate limit reached on audio seconds per hour (ASH). Please try again in 7m30s.")
        return SimpleNamespace(text="hello there")

    stt = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ai, "_stt_client", lambda: stt)
    monkeypatch.setattr(ai, "_cooling", {})
    monkeypatch.setattr(settings, "STT_MODEL", "whisper-large-v3")
    monkeypatch.setattr(settings, "AI_MOCK", False)
    monkeypatch.setattr(settings, "STT_API_KEY", "test")
    monkeypatch.setattr(settings, "LLM_API_KEY", "test")
    assert ai.transcribe(b"x", "a.webm", db=db) == "hello there"
    assert tried == ["whisper-large-v3", "whisper-large-v3-turbo"]
