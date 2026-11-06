"""Resume screening pipeline (runs as a background task right after a successful application).

1. stage -> under_review; flag another account using the same resume file or phone number
   must-have form answers missed => not_qualified with the reason (no AI call)
2. extract PDF text with pdfplumber; < 100 chars => screening_failed + manual review + notify recruiter
   the resume does not show the candidate's name => not_qualified (someone else's resume)
3. ask the LLM to parse + score the resume against the job (rubric in prompts.py)
4. save parsed data + scores; composite = resume_total for now (incomplete until the interview)
5. resume_total >= threshold => generate questions, create interview session, invite by email
   below the job's minimum degree / experience / CGPA, or below the threshold => not_qualified. The candidate sees
   the reason in My applications (no email)
6. any AI failure => screening_failed + manual review + notify recruiter
"""

import io
import logging
import uuid

from sqlalchemy import select

from app import database
from app.ai import client as ai
from app.ai import prompts
from app.ai.mock import mock_resume_screen
from app.ai.schemas import ResumeScreenResult
from app.config import settings
from app.models import Application, CandidateProfile, EvaluationScore, Resume
from app.models.enums import Stage
from app.schemas.form import must_have_failures
from app.services import evaluation
from app.services import profile as profile_svc
from app.services.application import set_stage
from app.services.interview import create_interview_session
from app.services.notification import Notifier
from app.services.storage import StorageError, get_storage

log = logging.getLogger(__name__)

MIN_TEXT_CHARS = 100
MAX_TEXT_CHARS = 12_000
UNREADABLE_REASON = "PDF has no readable text (possibly scanned)"


def extract_text(pdf_bytes: bytes) -> str:
    """Return all text in the PDF ('' if it cannot be read)."""
    try:
        import pdfplumber  # imported on first use: it is slow to load

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [(page.extract_text() or "") for page in pdf.pages[:20]]
    except Exception as exc:  # corrupted / encrypted PDFs
        log.warning("PDF extraction failed: %s", exc)
        return ""
    return "\n".join(pages).strip()


def _fail(db, application: Application, reason: str) -> None:
    set_stage(application, Stage.SCREENING_FAILED)
    application.needs_manual_review = True
    application.review_reason = reason
    db.commit()
    Notifier().recruiter_manual_review(
        application.job.recruiter.email,
        application.candidate.full_name,
        application.job.title,
        reason,
        str(application.id),
    )


def _not_qualified(db, application: Application, reason: str) -> None:
    """A hard rule failed (must-have answer, someone else's resume, minimum requirement). The candidate sees the
    reason at once; the recruiter can still invite them."""
    set_stage(application, Stage.NOT_QUALIFIED)
    application.review_reason = reason
    application.job.blocked_applications = (application.job.blocked_applications or 0) + 1
    db.commit()


def duplicate_flags(db, application: Application) -> list[str]:
    """Warnings for the recruiter when another account used the same resume file or phone number."""
    flags = []
    me = application.candidate_id
    file_hash = application.resume.file_hash if application.resume else None
    if file_hash and db.scalar(
        select(Resume.id)
        .join(Application, Application.id == Resume.application_id)
        .where(Resume.file_hash == file_hash, Application.candidate_id != me)
        .limit(1)
    ):
        flags.append("The same resume file was used by another account")
    phone = profile_svc.phone_digits((application.profile_snapshot or {}).get("phone"))
    if len(phone) >= 7:
        others = db.scalars(
            select(CandidateProfile.phone).where(CandidateProfile.user_id != me, CandidateProfile.phone.is_not(None))
        )
        if any(profile_svc.phone_digits(o) == phone for o in others):
            flags.append("The same phone number is on another account")
    return flags


def screen(application_id: uuid.UUID) -> None:
    """Background task entry point. Opens its own DB session (the request's session is closed by now)."""
    db = database.SessionLocal()
    try:
        _screen(db, application_id)
    except Exception:
        log.exception("Unexpected error while screening application %s", application_id)
        db.rollback()
        application = db.get(Application, application_id)
        if application is not None and application.stage == Stage.UNDER_REVIEW:
            _fail(db, application, "Unexpected error during automatic screening")
    finally:
        db.close()


def _screen(db, application_id: uuid.UUID) -> None:
    application = db.get(Application, application_id)
    if application is None:
        return
    job, resume = application.job, application.resume
    set_stage(application, Stage.UNDER_REVIEW)
    application.needs_manual_review = False
    application.review_reason = None
    flags = duplicate_flags(db, application)
    application.mismatches = flags
    db.commit()

    # Must-have answers in the job's form: no AI needed, so the candidate hears at once.
    missed = must_have_failures(job.application_form or [], application.form_answers or [])
    if missed:
        _not_qualified(
            db, application, "Your answers do not meet this job's must-have requirements: " + "; ".join(missed)
        )
        return

    try:
        pdf_bytes = get_storage().load(resume.file_key)
    except StorageError as exc:
        _fail(db, application, f"Resume file could not be loaded: {exc}")
        return

    text = extract_text(pdf_bytes)
    resume.raw_text = text
    if len(text) < MIN_TEXT_CHARS:
        resume.parse_ok = False
        _fail(db, application, UNREADABLE_REASON)
        return
    text = text[:MAX_TEXT_CHARS]
    name = application.candidate.full_name
    if settings.CHECK_RESUME_NAME and not profile_svc.resume_has_name(name, text):
        _not_qualified(
            db,
            application,
            f"The resume does not show your name ({name}). It looks like someone else's resume. "
            "Apply with your own resume, or correct the name on your profile.",
        )
        return

    claims = profile_svc.snapshot_as_answers(application.profile_snapshot) + (application.form_answers or [])
    try:
        result = ai.chat_json(
            prompts.RESUME_SCREEN_SYSTEM,
            prompts.resume_screen_user(job, text, claims),
            ResumeScreenResult,
            db=db,
            kind="resume_screen",
            application_id=application.id,
            mock=lambda: mock_resume_screen(job, text, claims),
        )
    except ai.AIServiceError as exc:
        resume.parse_ok = False
        _fail(db, application, f"AI screening failed: {exc}")
        return

    resume.parse_ok = True
    claims = {**(application.profile_snapshot or {}), **profile_svc.form_claims(application.form_answers)}
    application.mismatches = (
        profile_svc.compare_with_resume(claims, result.education_level, result.years_experience) + flags
    )
    resume.parsed = {
        "education_level": result.education_level,
        "skills": result.skills,
        "matched_skills": result.matched_skills,
        "missing_skills": result.missing_skills,
        "years_experience": result.years_experience,
        "education": result.education,
        "cgpa": result.cgpa,
        "certifications": result.certifications,
        "summary": result.summary,
    }
    total = evaluation.resume_total(result.skill_score, result.experience_score, result.education_score)
    score = application.evaluation or EvaluationScore(application_id=application.id)
    score.skill_score = round(result.skill_score, 1)
    score.experience_score = round(result.experience_score, 1)
    score.education_score = round(result.education_score, 1)
    score.resume_total = total
    score.interview_score = None
    score.composite_score = evaluation.composite_score(total, None)
    score.resume_reasoning = result.reasoning_text()
    score.incomplete = True
    db.add(score)
    db.commit()

    # Strict check of the job's minimum degree, experience and CGPA, against what the resume itself shows.
    failed = [
        c
        for c in profile_svc.requirements(job, result.education_level, result.years_experience, result.cgpa)
        if not c["ok"]
    ]
    if failed:
        _not_qualified(
            db,
            application,
            "Does not meet the minimum requirements: "
            + "; ".join(f"{c['label']} needs {c['required']}, the resume shows {c['yours']}" for c in failed),
        )
        return
    if total < job.screening_threshold:
        set_stage(application, Stage.NOT_QUALIFIED)
        db.commit()
        return

    try:
        session = create_interview_session(db, application, resume.parsed)
    except ai.AIServiceError as exc:
        _fail(db, application, f"AI question generation failed: {exc}")
        return
    set_stage(application, Stage.INTERVIEW_INVITED)
    db.commit()
    candidate = application.candidate
    Notifier().interview_invitation(candidate.email, candidate.full_name, job.title, str(session.id))
