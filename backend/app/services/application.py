"""Applications: the stage state machine, applying with a resume upload, and candidate-facing views."""

import hashlib
import json
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Application, Job, Resume, User
from app.models.enums import Role, SessionStatus, Stage
from app.schemas.form import check_answers
from app.services import profile as profile_svc
from app.services.job import is_open_for_applications
from app.services.notification import Notifier
from app.services.storage import get_storage

MAX_RESUME_BYTES = 5 * 1024 * 1024

# --- Stage state machine: the ONLY place stage changes are validated ---------------------------
STAGE_TRANSITIONS: dict[Stage, set[Stage]] = {
    Stage.SUBMITTED: {Stage.UNDER_REVIEW},
    Stage.UNDER_REVIEW: {Stage.SCREENING_FAILED, Stage.NOT_QUALIFIED, Stage.INTERVIEW_INVITED},
    # recruiter re-runs screening, or invites the candidate anyway after reading the resume
    Stage.SCREENING_FAILED: {Stage.UNDER_REVIEW, Stage.INTERVIEW_INVITED},
    Stage.NOT_QUALIFIED: {Stage.INTERVIEW_INVITED},  # recruiter overrides the AI and invites manually
    Stage.INTERVIEW_INVITED: {Stage.INTERVIEW_IN_PROGRESS},
    Stage.INTERVIEW_IN_PROGRESS: {Stage.EVALUATED},
    Stage.EVALUATED: set(),
}


class InvalidTransition(Exception):
    pass


def set_stage(application: Application, new_stage: Stage) -> None:
    current = Stage(application.stage)
    if new_stage not in STAGE_TRANSITIONS[current]:
        raise InvalidTransition(f"Invalid stage change {current.value} -> {new_stage.value}")
    application.stage = new_stage.value


# --- Candidate-facing labels (never show scores) -----------------------------------------------------
CANDIDATE_VIEW: dict[Stage, tuple[str, int]] = {
    Stage.SUBMITTED: ("Submitted", 1),
    Stage.UNDER_REVIEW: ("Under review", 2),
    Stage.SCREENING_FAILED: ("Under review", 2),
    Stage.NOT_QUALIFIED: ("Not selected", 2),
    Stage.INTERVIEW_INVITED: ("Interview invited", 3),
    Stage.INTERVIEW_IN_PROGRESS: ("Interview in progress", 3),
    Stage.EVALUATED: ("Evaluated", 5),
}


# --- Upload validation ----------------------------------------------------------------------------
def validate_pdf(upload: UploadFile, data: bytes) -> None:
    name = (upload.filename or "").lower()
    ctype = (upload.content_type or "").split(";")[0].strip().lower()
    if (
        not name.endswith(".pdf")
        or ctype not in {"application/pdf", "application/x-pdf"}
        or not data.startswith(b"%PDF")
    ):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Resume must be a PDF file")
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Resume must be 5 MB or smaller")


async def read_limited(upload: UploadFile, limit: int) -> bytes:
    """Read at most limit+1 bytes so a huge upload is rejected without loading it all into memory."""
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File must be {limit // (1024 * 1024)} MB or smaller"
        )
    return data


def parse_answers(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Form answers are not valid JSON") from None
    if not isinstance(value, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Form answers must be an object")
    return value


def apply(
    db: Session,
    job: Job,
    candidate: User,
    upload: UploadFile | None,
    data: bytes | None,
    answers: dict | None = None,
) -> Application:
    """Apply with the profile's resume, or with a different PDF uploaded for this job only."""
    from app.services.auth import require_verified

    require_verified(candidate)
    if not is_open_for_applications(job):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This job is not accepting applications")
    if db.scalar(select(Application).where(Application.job_id == job.id, Application.candidate_id == candidate.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already applied to this job")
    check = profile_svc.eligibility(job, candidate.profile)
    if not check["profile_complete"]:
        missing = ", ".join(profile_svc.missing_fields(candidate.profile))
        raise HTTPException(status.HTTP_409_CONFLICT, f"Complete your profile before applying. Missing: {missing}")
    if upload is not None and data is not None:
        validate_pdf(upload, data)
        filename = upload.filename or "resume.pdf"
    else:
        data = profile_svc.load_file(candidate.profile.resume_key)
        filename = candidate.profile.resume_filename or "resume.pdf"
    try:
        form_answers = check_answers(job.application_form or [], answers or {})
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        stage=Stage.SUBMITTED.value,
        form_answers=form_answers,
        profile_snapshot=profile_svc.snapshot(candidate),
    )
    db.add(application)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already applied to this job") from None

    key = f"resumes/{job.id}/{application.id}.pdf"
    get_storage().save(key, data, "application/pdf")
    safe_name = filename.replace("/", "_")[-200:]
    db.add(
        Resume(
            application_id=application.id,
            file_key=key,
            original_filename=safe_name,
            file_hash=hashlib.sha256(data).hexdigest(),
        )
    )
    db.commit()

    Notifier().application_received(candidate.email, candidate.full_name, job.title)
    return application


def get_application_for_user(db: Session, application_id: uuid.UUID, user: User) -> Application:
    """Recruiter must own the job; candidate must own the application. Otherwise 404."""
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if user.role == Role.RECRUITER and application.job.recruiter_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if user.role == Role.CANDIDATE and application.candidate_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


THRESHOLD_REASON = "Your resume does not match this job's required skills and experience closely enough."


def candidate_reason(a: Application) -> str | None:
    """Why the candidate was not selected, in words they can act on. Scores are never shown."""
    if a.stage != Stage.NOT_QUALIFIED:
        return None
    return a.review_reason or THRESHOLD_REASON


def my_applications(db: Session, candidate: User) -> list[dict]:
    apps = db.scalars(
        select(Application).where(Application.candidate_id == candidate.id).order_by(Application.created_at.desc())
    )
    out = []
    for a in apps:
        label, step = CANDIDATE_VIEW[Stage(a.stage)]
        # A shortlist is good news, so the candidate sees it. A recruiter's own "rejected" is never shown.
        shortlisted = a.recruiter_decision == "shortlisted"
        if shortlisted:
            label = "Shortlisted"
        session = a.interview
        can_start = (
            session is not None
            and not a.archived
            and a.stage in (Stage.INTERVIEW_INVITED, Stage.INTERVIEW_IN_PROGRESS)
            and session.status != SessionStatus.COMPLETED
        )
        out.append(
            {
                "id": a.id,
                "job_id": a.job_id,
                "job_title": a.job.title,
                "job_status": a.job.status,
                "status_label": label,
                "stage_step": step,
                "applied_at": a.created_at,
                "updated_at": a.updated_at,
                "interview_session_id": session.id if session else None,
                "interview_status": session.status if session else None,
                "can_start_interview": can_start,
                "shortlisted": shortlisted,
                "reason": candidate_reason(a),
            }
        )
    return out
