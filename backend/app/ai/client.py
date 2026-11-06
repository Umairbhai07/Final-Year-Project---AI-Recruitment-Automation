"""The ONLY place that talks to the AI provider (Groq via the OpenAI-compatible SDK).

- chat_json(): LLM call in JSON mode, temperature 0, Pydantic validation (+ score clamping),
  tenacity retries (3 tries, exponential backoff) on network errors, 429, 5xx and invalid JSON.
- transcribe(): speech-to-text with Whisper.
- Every attempt is written to the insert-only ai_audit_log table.
- AI_MOCK mode: the caller passes a `mock` function returning deterministic fake output, which still
  goes through the same validation + audit path, so the app works fully without an API key.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from tenacity import RetryError, retry, retry_if_exception, wait_exponential

from app.config import settings
from app.services.audit import write_audit

if TYPE_CHECKING:
    import openai

log = logging.getLogger(__name__)


def _oa():
    """The openai SDK, imported on first use: it takes about 0.4 s and most requests never need it."""
    return importlib.import_module("openai")


T = TypeVar("T", bound=BaseModel)


class AIServiceError(Exception):
    """Raised when the AI provider fails after all retries."""


class InvalidAIOutput(Exception):
    """The model answered, but the output was not usable (bad JSON / wrong shape). Triggers a retry."""


def _retryable(exc: BaseException) -> bool:
    oa = _oa()
    return isinstance(
        exc,
        oa.APIConnectionError | oa.RateLimitError | oa.InternalServerError | InvalidAIOutput,
    )


# Tests replace WAIT_STRATEGY with wait_none() so retries don't slow the test suite.
WAIT_STRATEGY = wait_exponential(multiplier=1, min=1, max=8)
RESPECT_RATE_LIMIT_DELAY = True  # tests turn this off


# A 429 that asks us to wait longer than this is a daily (or hourly) limit, not the per-minute one: waiting would
# not help, so the request moves to the next model, which has its own separate free-tier limits.
LONG_LIMIT_SECONDS = 20.0
# Total time one AI call may spend retrying. Vercel stops a request after 120 s, and when we give up the work is
# kept safely (answer scored later, resume sent to manual review) instead of the request being killed half-way.
RETRY_BUDGET_SECONDS = 50.0


def rate_limit_delay(exc: BaseException | None, cap: float | None = 60.0) -> float | None:
    """Seconds Groq asks us to wait after a 429 ("Please try again in 3.15s" / retry-after header)."""
    if not isinstance(exc, _oa().RateLimitError):
        return None
    header = getattr(getattr(exc, "response", None), "headers", {}) or {}
    secs: float | None = None
    try:
        secs = float(header.get("retry-after"))
    except (TypeError, ValueError):
        m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)(ms|s)", str(exc))
        if not m:
            secs = 10.0
        else:
            secs = float(m.group(3)) / (1000 if m.group(4) == "ms" else 1)
            secs += 3600 * int(m.group(1) or 0) + 60 * int(m.group(2) or 0)
    return secs if cap is None else min(secs, cap)


_cooling: dict[str, float] = {}  # model -> time.monotonic() when its long rate limit ends


def _cooling_down(name: str) -> bool:
    return _cooling.get(name, 0.0) > time.monotonic()


def _note_long_limit(name: str, exc: Exception) -> bool:
    """True if `exc` is a long rate limit for `name`; the model is then skipped until the limit ends."""
    delay = rate_limit_delay(exc, cap=None)
    if delay is None or delay <= LONG_LIMIT_SECONDS:
        return False
    _cooling[name] = time.monotonic() + delay
    log.warning("Model %s hit a long rate limit (%.0f s); using the next model", name, delay)
    return True


def _wait(retry_state) -> float:
    delay = None
    if RESPECT_RATE_LIMIT_DELAY and retry_state.outcome is not None:
        delay = rate_limit_delay(retry_state.outcome.exception())
    wait = delay + 0.5 if delay is not None else WAIT_STRATEGY(retry_state)
    return max(0.0, min(wait, RETRY_BUDGET_SECONDS - (retry_state.seconds_since_start or 0.0)))


def _stop(retry_state) -> bool:
    """3 tries normally; up to 8 when the free-tier per-minute token limit is hit (it clears within a minute)."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    limit = 8 if isinstance(exc, _oa().RateLimitError) else 3
    return retry_state.attempt_number >= limit or (retry_state.seconds_since_start or 0.0) >= RETRY_BUDGET_SECONDS


_retry = retry(
    reraise=False,
    stop=_stop,
    wait=_wait,
    retry=retry_if_exception(_retryable),
)


def _llm_client() -> openai.OpenAI:
    return _oa().OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY or "missing",
        timeout=settings.AI_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _stt_client() -> openai.OpenAI:
    return _oa().OpenAI(
        base_url=settings.STT_BASE_URL,
        api_key=settings.STT_API_KEY or settings.LLM_API_KEY or "missing",
        timeout=settings.AI_TIMEOUT_SECONDS,
        max_retries=0,
    )


# Chat models to try, best first, when LLM_MODEL is retired or not enabled for the account.
# Groq retires models from time to time; this keeps the app working without editing .env.
FALLBACK_MODELS = (
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905",
    "moonshotai/kimi-k2-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
)
_NOT_CHAT = ("whisper", "guard", "tts", "playai", "orpheus", "distil", "prompt-guard", "compound", "allam")
_working_model: str | None = None
_dead_models: set[str] = set()
_available: list[str] | None = None


def candidate_models(client: openai.OpenAI | None = None) -> list[str]:
    """LLM_MODEL first, then known-good fallbacks the account can see, then any other chat model."""
    names = [settings.LLM_MODEL, *FALLBACK_MODELS]
    global _available
    if _available is None:
        try:
            _available = [m.id for m in (client or _llm_client()).models.list().data]
        except Exception:  # listing is optional; keep the static list
            _available = []
    available = _available
    if available:
        names = [n for n in names if n in available or n == settings.LLM_MODEL]
        names += [m for m in available if not any(x in m.lower() for x in _NOT_CHAT)]
    seen: list[str] = []
    for n in names:
        if n and n not in seen and n not in _dead_models:
            seen.append(n)
    return seen


def _is_missing_model(exc: Exception) -> bool:
    text = str(exc).lower()
    return isinstance(exc, _oa().NotFoundError | _oa().BadRequestError | _oa().PermissionDeniedError) and (
        "model" in text and ("not exist" in text or "not found" in text or "decommission" in text or "access" in text)
    )


def _chat_completion(**kwargs):
    """chat.completions.create with automatic switch to another model if the configured one is gone."""
    global _working_model
    client = _llm_client()

    def names():
        yield settings.LLM_MODEL  # tried before asking Groq for the model list; back in use once its limit ends
        if _working_model:
            yield _working_model
        yield from candidate_models(client)

    last: Exception | None = None
    limited = False
    tried: set[str] = set()
    for name in names():
        if name in tried or name in _dead_models or _cooling_down(name):
            continue
        tried.add(name)
        extra = {"reasoning_effort": "low"} if "gpt-oss" in name else None  # fewer tokens, same JSON quality
        try:
            resp = client.chat.completions.create(model=name, extra_body=extra, **kwargs)
        except Exception as exc:
            if isinstance(exc, _oa().RateLimitError) and _note_long_limit(name, exc):
                limited = True
                continue
            if not _is_missing_model(exc):
                raise
            log.warning("LLM model %s is not available (%s); trying the next one", name, exc)
            _dead_models.add(name)
            if _working_model == name:
                _working_model = None
            last = exc
            continue
        if name != settings.LLM_MODEL and _working_model != name:
            log.warning("Using LLM model %s because %s is not available", name, settings.LLM_MODEL)
        _working_model = name
        return resp
    if limited or any(_cooling_down(n) for n in tried | {settings.LLM_MODEL}):
        raise AIServiceError("Every AI model has reached its free-tier limit for now; the work is kept for later")
    raise last or AIServiceError("No language model is available for this API key")


def _parse_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):  # tolerate ```json fences
        text = text.strip("`")
        text = text[text.find("{") :]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidAIOutput(f"Model did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidAIOutput("Model JSON is not an object")
    return data


def chat_json(
    system: str,
    user: str,
    schema: type[T],
    *,
    db: Session,
    kind: str,
    application_id: uuid.UUID | None = None,
    mock: Callable[[], dict] | None = None,
    extra_check: Callable[[T], None] | None = None,
) -> T:
    """Call the LLM and return a validated `schema` instance. Raises AIServiceError on final failure."""
    use_mock = settings.ai_mock_effective and mock is not None

    @_retry
    def attempt() -> T:
        model_name = "mock" if use_mock else (_working_model or settings.LLM_MODEL)
        raw = None
        try:
            if use_mock:
                raw = json.dumps(mock())
            else:
                resp = _chat_completion(
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                raw = resp.choices[0].message.content or ""
            try:
                result = schema.model_validate(_parse_json(raw))
            except ValidationError as exc:
                raise InvalidAIOutput(f"Model JSON has the wrong shape: {exc.error_count()} errors") from exc
            if extra_check:
                extra_check(result)
            return result
        except Exception as exc:
            log.warning("AI %s attempt failed: %s", kind, exc)
            raise
        finally:
            write_audit(
                db,
                application_id=application_id,
                kind=kind,
                model=model_name,
                input_text=f"SYSTEM:\n{system}\n\nUSER:\n{user}",
                raw_output=raw,
            )

    try:
        return attempt()
    except RetryError as exc:
        raise AIServiceError(str(exc.last_attempt.exception())) from exc
    except _oa().APIError as exc:  # non-retryable provider errors (401, 400, ...)
        raise AIServiceError(f"{type(exc).__name__}: {exc}") from exc


STT_FALLBACK_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")  # separate free-tier limits


def _transcription(audio: bytes, filename: str):
    """Whisper call that moves to the other Whisper model when one has hit a long rate limit."""
    names = [settings.STT_MODEL, *(m for m in STT_FALLBACK_MODELS if m != settings.STT_MODEL)]
    for name in names:
        if _cooling_down(name):
            continue
        try:
            resp = _stt_client().audio.transcriptions.create(
                model=name, file=(filename, audio), response_format="json", language="en"
            )
            return name, resp
        except Exception as exc:
            if isinstance(exc, _oa().RateLimitError) and _note_long_limit(name, exc):
                continue
            raise
    raise AIServiceError("Every speech model has reached its free-tier limit for now; the answer is kept for later")


def transcribe(
    audio: bytes,
    filename: str,
    *,
    db: Session,
    application_id: uuid.UUID | None = None,
    mock: Callable[[], str] | None = None,
) -> str:
    """Speech-to-text. Returns the transcript (may be empty). Raises AIServiceError on final failure."""
    use_mock = settings.ai_mock_effective and mock is not None
    model_name = "mock" if use_mock else settings.STT_MODEL

    @_retry
    def attempt() -> str:
        nonlocal model_name
        text = None
        try:
            if use_mock:
                text = mock()
            else:
                model_name, resp = _transcription(audio, filename)
                text = (getattr(resp, "text", None) or "").strip()
            return text
        finally:
            write_audit(
                db,
                application_id=application_id,
                kind="transcribe",
                model=model_name,
                input_text=f"audio file {filename} ({len(audio)} bytes)",
                raw_output=text,
            )

    try:
        return attempt()
    except RetryError as exc:
        raise AIServiceError(str(exc.last_attempt.exception())) from exc
    except _oa().APIError as exc:
        raise AIServiceError(f"{type(exc).__name__}: {exc}") from exc
