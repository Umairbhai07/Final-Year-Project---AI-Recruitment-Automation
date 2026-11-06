"""AI voice interview: question generation, session state, answer upload -> transcribe -> evaluate -> score."""

import hmac
import logging
import math
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai import client as ai
from app.ai import prompts
from app.ai.mock import mock_answer_eval, mock_follow_up, mock_questions, mock_transcript
from app.ai.schemas import AnswerEvaluation, FollowUpQuestion, QuestionSet
from app.core.security import hash_token
from app.models import Application, InterviewResponse, InterviewSession, User
from app.models.enums import SessionStatus, Stage
from app.services import evaluation, integrity
from app.services.application import set_stage
from app.services.notification import Notifier
from app.services.storage import get_storage

log = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 10 * 1024 * 1024
AUDIO_EXTENSIONS = {".webm", ".ogg", ".mp4", ".m4a", ".wav", ".mp3", ".mpeg", ".mpga"}
AUDIO_MIME = {
    "audio/webm",
    "video/webm",
    "audio/ogg",
    "audio/mp4",
    "video/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
}
MIN_MEANINGFUL_WORDS = 3
NO_ANSWER_FEEDBACK = "No meaningful answer detected."
TIME_EXPIRED_FEEDBACK = "No answer: the time ran out before an answer was recorded."
GRACE_SECONDS = 20  # network / browser slack on top of speaking + thinking + answering time
UPLOAD_GRACE_SECONDS = 90  # an answer uploaded later than this after the deadline is flagged as late


def generate_questions(db: Session, application: Application, parsed: dict) -> list[dict]:
    job = application.job
    n = job.num_questions

    def check_count(result: QuestionSet) -> None:
        if len(result.questions) != n:
            raise ai.InvalidAIOutput(f"Expected {n} questions, got {len(result.questions)}")

    result = ai.chat_json(
        prompts.QUESTION_GEN_SYSTEM,
        prompts.question_gen_user(job, parsed, n),
        QuestionSet,
        db=db,
        kind="question_gen",
        application_id=application.id,
        mock=lambda: mock_questions(job, parsed, n),
        extra_check=check_count,
    )
    return [
        {"index": i, "text": q.text.strip(), "focus": q.focus.strip(), "kind": "main"}
        for i, q in enumerate(result.questions)
    ]


def create_interview_session(db: Session, application: Application, parsed: dict) -> InterviewSession:
    questions = generate_questions(db, application, parsed)
    session = application.interview
    if session is None:
        session = InterviewSession(application_id=application.id)
        db.add(session)
    session.questions = questions
    session.status = SessionStatus.INVITED.value
    session.current_index = 0
    session.invited_at = datetime.now(UTC)
    session.question_served_at = None
    session.integrity_events = []
    session.snapshots = []
    session.terminated = False
    session.terminated_reason = None
    db.flush()
    return session


def get_session_for_candidate(db: Session, session_id, user: User) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if session is None or session.application.candidate_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return session


def speak_seconds(text: str) -> int:
    """Time allowed for the browser to read the question aloud (about 2.2 words per second)."""
    return math.ceil(len(text.split()) / 2.2) + 3


def question_budget(session: InterviewSession, index: int) -> int:
    """Total seconds for one question: hearing it + thinking + answering + slack."""
    job = session.application.job
    return (
        speak_seconds(session.questions[index]["text"]) + job.think_seconds + job.seconds_per_question + GRACE_SECONDS
    )


def _elapsed(session: InterviewSession) -> float:
    served = session.question_served_at
    if served is None:
        return 0.0
    if served.tzinfo is None:  # SQLite returns naive datetimes
        served = served.replace(tzinfo=UTC)
    return (datetime.now(UTC) - served).total_seconds()


def _serve_current(session: InterviewSession) -> None:
    session.question_served_at = datetime.now(UTC) if session.current_index < len(session.questions) else None


def state(session: InterviewSession) -> dict:
    app = session.application
    total = len(session.questions)
    can_answer = (
        session.status != SessionStatus.COMPLETED
        and not app.archived
        and app.stage in (Stage.INTERVIEW_INVITED, Stage.INTERVIEW_IN_PROGRESS)
    )
    current_q = session.questions[session.current_index] if session.current_index < total else None
    seconds_left = None
    if current_q is not None and session.status == SessionStatus.IN_PROGRESS:
        seconds_left = max(0, int(question_budget(session, session.current_index) - _elapsed(session)))
    return {
        "session_id": session.id,
        "device_locked": session.device_token_hash is not None,
        "job_title": app.job.title,
        "status": session.status,
        "total_questions": total,
        "current_index": session.current_index,
        "current_question": current_q["text"] if (current_q and can_answer) else None,
        "current_kind": (current_q or {}).get("kind", "main") if can_answer else None,
        "seconds_per_question": app.job.seconds_per_question,
        "think_seconds": app.job.think_seconds,
        "seconds_left": seconds_left,
        "follow_ups_planned": app.job.follow_up_questions,
        "strikes": integrity.strikes(session),
        "max_strikes": integrity.MAX_STRIKES,
        "terminated": bool(session.terminated),
        "require_webcam": bool(app.job.require_webcam),
        "can_answer": can_answer,
    }


def _ensure_available(session: InterviewSession) -> None:
    app = session.application
    if session.status == SessionStatus.COMPLETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is already completed")
    if app.archived or app.stage not in (Stage.INTERVIEW_INVITED, Stage.INTERVIEW_IN_PROGRESS):
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is not available")


OTHER_DEVICE = (
    "This interview is already open on another device or browser. Continue there, or ask the recruiter to "
    "allow a new device."
)


def _device_ok(session: InterviewSession, token: str | None) -> bool:
    return session.device_token_hash is None or (
        token is not None and hmac.compare_digest(session.device_token_hash, hash_token(token))
    )


def check_device(db: Session, session: InterviewSession, token: str | None) -> None:
    """Every interview request must come from the browser that started it."""
    if not _device_ok(session, token):
        if session.status == SessionStatus.IN_PROGRESS:
            integrity.add_event(session, "second_device", session.current_index)
            db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, OTHER_DEVICE)


def start(db: Session, session: InterviewSession, device_token: str | None = None) -> dict:
    """Starts (or resumes on the same device). The first start locks the interview to this browser and returns
    a secret device token that the browser sends with every later request."""
    _ensure_available(session)
    new_token = None
    if session.device_token_hash is None:
        new_token = secrets.token_urlsafe(32)
        session.device_token_hash = hash_token(new_token)
    else:
        check_device(db, session, device_token)
    if session.status == SessionStatus.INVITED:
        session.status = SessionStatus.IN_PROGRESS.value
        session.started_at = datetime.now(UTC)
        set_stage(session.application, Stage.INTERVIEW_IN_PROGRESS)
        _serve_current(session)
        db.commit()
    elif session.question_served_at is None:
        _serve_current(session)
        db.commit()
    else:
        db.commit()
    return {**state(session), "device_token": new_token}


def release_device(db: Session, session: InterviewSession) -> None:
    """Recruiter lets the candidate continue on a new device (e.g. their laptop broke)."""
    session.device_token_hash = None
    integrity.add_event(session, "device_reset", session.current_index, "Recruiter allowed a new device")
    db.commit()


def _validate_audio(upload: UploadFile, data: bytes) -> str:
    name = (upload.filename or "answer.webm").lower()
    ext = name[name.rfind(".") :] if "." in name else ""
    ctype = (upload.content_type or "").split(";")[0].strip().lower()
    if ext not in AUDIO_EXTENSIONS or ctype not in AUDIO_MIME:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Audio must be webm, ogg, mp4, m4a, wav or mp3")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio must be 10 MB or smaller")
    if len(data) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio file is empty")
    return ext


def submit_answer(
    db: Session,
    session: InterviewSession,
    question_index: int,
    upload: UploadFile,
    data: bytes,
    attention: float | None = None,
) -> dict:
    _ensure_available(session)
    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start the interview first")
    if question_index != session.current_index:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Answers must be submitted in order. Expected question {session.current_index + 1}",
        )
    ext = _validate_audio(upload, data)
    question = session.questions[question_index]
    if (
        session.question_served_at
        and _elapsed(session) > question_budget(session, question_index) + UPLOAD_GRACE_SECONDS
    ):
        integrity.add_event(session, "late_answer", question_index, f"{int(_elapsed(session))} s after the question")
    if attention is not None:  # webcam: share of the answer spent looking at the screen
        integrity.add_event(session, "attention", question_index, None, round(attention, 1))

    key = f"audio/{session.id}/{question_index}{ext}"
    get_storage().save(key, data, upload.content_type or "audio/webm")

    response = InterviewResponse(session_id=session.id, question_index=question_index, audio_key=key)
    db.add(response)
    # Transcribe + evaluate now. If the AI is busy or down (after its retries), the answer is kept and scored
    # later, so the candidate can carry on instead of seeing an error.
    try:
        transcript = _score(db, session, question, response, data, ext)
    except ai.AIServiceError as exc:
        log.warning("Answer %s of %s will be scored later: %s", question_index, session.id, exc)
        response.pending = True
        response.transcript = None
        response.feedback = PENDING_FEEDBACK
        transcript = None
    if transcript and len(transcript.split()) >= MIN_MEANINGFUL_WORDS:
        _maybe_add_follow_up(db, session, question_index, transcript)
    return _advance(db, session, question_index)


PENDING_FEEDBACK = "Scoring in progress: the AI service was busy, so this answer is scored a little later."


def _score(db: Session, session: InterviewSession, question: dict, response: InterviewResponse, data: bytes, ext: str):
    """Transcribe and evaluate one answer into `response`. Raises AIServiceError if the AI fails."""
    app = session.application
    job = app.job
    transcript = ai.transcribe(
        data, f"answer{ext}", db=db, application_id=app.id, mock=lambda: mock_transcript(data, question)
    )
    if len((transcript or "").split()) < MIN_MEANINGFUL_WORDS:
        acc = rel = cla = 0.0
        feedback = NO_ANSWER_FEEDBACK
    else:
        result = ai.chat_json(
            prompts.ANSWER_EVAL_SYSTEM,
            prompts.answer_eval_user(job, question, transcript),
            AnswerEvaluation,
            db=db,
            kind="answer_eval",
            application_id=app.id,
            mock=lambda: mock_answer_eval(job, question, transcript),
        )
        acc, rel, cla, feedback = result.accuracy, result.relevance, result.clarity, result.feedback
    response.transcript = transcript or ""
    response.accuracy = round(acc, 1)
    response.relevance = round(rel, 1)
    response.clarity = round(cla, 1)
    response.score = evaluation.answer_score(acc, rel, cla)  # computed server-side, model arithmetic not trusted
    response.feedback = feedback
    response.pending = False
    return transcript


def score_pending(db: Session, session: InterviewSession) -> int:
    """Try again to score answers the AI could not score at the time. Returns how many are still waiting."""
    waiting = [r for r in session.responses if r.pending]
    if not waiting:
        return 0
    by_index = {q["index"]: q for q in session.questions}
    left = 0
    for r in waiting:
        try:
            data = get_storage().load(r.audio_key)
            _score(db, session, by_index[r.question_index], r, data, "." + r.audio_key.rsplit(".", 1)[-1])
        except Exception as exc:  # still busy: try again next time
            log.warning("Pending answer %s still not scored: %s", r.question_index, exc)
            left += 1
    if session.status == SessionStatus.COMPLETED:
        _update_scores(session)
    db.commit()
    return left


def skip_question(db: Session, session: InterviewSession, question_index: int) -> dict:
    """The timer ran out with nothing recorded (e.g. the page was reopened too late): score the question 0."""
    _ensure_available(session)
    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start the interview first")
    if question_index != session.current_index:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Expected question {session.current_index + 1}")
    integrity.add_event(session, "time_expired", question_index)
    db.add(
        InterviewResponse(
            session_id=session.id,
            question_index=question_index,
            audio_key=None,
            transcript="",
            score=0.0,
            feedback=TIME_EXPIRED_FEEDBACK,
        )
    )
    return _advance(db, session, question_index)


def _advance(db: Session, session: InterviewSession, question_index: int) -> dict:
    session.current_index = question_index + 1
    total = len(session.questions)
    if session.current_index < total:
        _serve_current(session)
        db.commit()
        nxt = session.questions[session.current_index]
        return {
            "completed": False,
            "next_index": session.current_index,
            "next_question": nxt["text"],
            "next_kind": nxt.get("kind", "main"),
            "total_questions": total,
            "seconds_left": question_budget(session, session.current_index),
        }
    _finish(db, session)
    return {"completed": True, "next_index": None, "next_question": None, "total_questions": total}


def _follow_up_targets(main_count: int, wanted: int) -> list[int]:
    """Which main questions (1-based) get a follow-up: spread out, never the last (behavioural) one."""
    pool = max(main_count - 1, 0)
    wanted = min(wanted, pool)
    return sorted({max(1, math.floor((k + 1) * pool / (wanted + 1))) for k in range(wanted)})


def _maybe_add_follow_up(db: Session, session: InterviewSession, question_index: int, transcript: str) -> None:
    job = session.application.job
    questions = list(session.questions)
    question = questions[question_index]
    if job.follow_up_questions <= 0 or question.get("kind", "main") != "main":
        return
    mains = [q for q in questions if q.get("kind", "main") == "main"]
    main_no = sum(1 for q in questions[: question_index + 1] if q.get("kind", "main") == "main")
    if main_no >= len(mains):  # never after the final question
        return
    used = sum(1 for q in questions if q.get("kind") == "follow_up")
    due = sum(1 for t in _follow_up_targets(len(mains), job.follow_up_questions) if t <= main_no)
    if used >= due:
        return
    try:
        result = ai.chat_json(
            prompts.FOLLOW_UP_SYSTEM,
            prompts.follow_up_user(job, question, transcript),
            FollowUpQuestion,
            db=db,
            kind="follow_up",
            application_id=session.application_id,
            mock=lambda: mock_follow_up(question, transcript),
        )
    except ai.AIServiceError as exc:  # the interview goes on without it
        log.warning("Follow-up question failed, continuing without it: %s", exc)
        return
    follow = {
        "text": result.text.strip(),
        "focus": f"Follow-up: {question.get('focus', '')}".strip(),
        "kind": "follow_up",
    }
    follow["parent_index"] = question_index
    questions.insert(question_index + 1, follow)
    session.questions = [{**q, "index": i} for i, q in enumerate(questions)]


MAX_SNAPSHOT_BYTES = 300 * 1024


def add_snapshot(db: Session, session: InterviewSession, data: bytes, reason: str, question_index: int | None) -> dict:
    """Store one small webcam photo taken by the browser (at the start, at random, or when something was flagged)."""
    if session.status != SessionStatus.IN_PROGRESS or session.terminated:
        raise HTTPException(status.HTTP_409_CONFLICT, "The interview is not running")
    if reason not in integrity.SNAPSHOT_REASONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown snapshot reason")
    if not data.startswith(b"\xff\xd8\xff"):  # JPEG magic bytes
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Snapshot must be a JPEG image")
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Snapshot is too large")
    snaps = list(session.snapshots or [])
    if len(snaps) >= integrity.MAX_SNAPSHOTS:
        return {"stored": False, "count": len(snaps)}
    index = len(snaps)
    key = f"snapshots/{session.id}/{index}.jpg"
    get_storage().save(key, data, "image/jpeg")
    snaps.append(
        {
            "index": index,
            "key": key,
            "at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "question_index": question_index,
        }
    )
    session.snapshots = snaps
    db.commit()
    return {"stored": True, "count": len(snaps)}


def record_events(db: Session, session: InterviewSession, events: list[dict]) -> dict:
    """Store lockdown events from the browser; end the interview at MAX_STRIKES."""
    if session.status == SessionStatus.IN_PROGRESS and not session.terminated:
        for e in events:
            integrity.add_event(session, e["type"], e.get("question_index"), e.get("detail"), e.get("value"))
        n = integrity.strikes(session)
        if n >= integrity.MAX_STRIKES:
            kinds = sorted(
                {
                    integrity.LABELS.get(e["type"], e["type"]).lower()
                    for e in session.integrity_events
                    if e.get("strike")
                }
            )
            reason = f"Reached {n} warnings (limit {integrity.MAX_STRIKES}): {', '.join(kinds)}."
            session.terminated = True
            session.terminated_reason = reason
            integrity.add_event(session, "terminated", session.current_index, reason)
            _finish(db, session)
        else:
            db.commit()
    return {
        "strikes": integrity.strikes(session),
        "max_strikes": integrity.MAX_STRIKES,
        "terminated": session.terminated,
    }


def _update_scores(session: InterviewSession) -> None:
    scores = [r.score for r in session.responses]
    if session.terminated:  # unanswered questions count as 0
        scores += [0.0] * max(0, len(session.questions) - len(scores))
    ev = session.application.evaluation
    ev.interview_score = evaluation.interview_score(scores)
    ev.composite_score = evaluation.composite_score(ev.resume_total, ev.interview_score)
    ev.incomplete = any(r.pending for r in session.responses)


def _finish(db: Session, session: InterviewSession) -> None:
    db.flush()
    db.refresh(session)
    app = session.application
    if any(r.pending for r in session.responses):
        score_pending(db, session)
    _update_scores(session)
    session.status = SessionStatus.COMPLETED.value
    session.completed_at = datetime.now(UTC)
    set_stage(app, Stage.EVALUATED)
    db.commit()
    notifier = Notifier()
    notifier.interview_completed(app.candidate.email, app.candidate.full_name, app.job.title)
    notifier.recruiter_candidate_evaluated(app.job.recruiter.email, app.candidate.full_name, app.job.title, str(app.id))


def report_issue(db: Session, session: InterviewSession, text: str) -> None:
    session.issue_reported = True
    session.issue_text = ((session.issue_text + "\n---\n") if session.issue_text else "") + text.strip()
    db.commit()
