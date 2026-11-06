import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_recruiter
from app.database import get_db
from app.models import User
from app.models.enums import Decision, Stage
from app.schemas.application import ApplicationDetailOut, CandidateRow, DecisionIn, JobStatsOut, OverviewOut
from app.services import dashboard as svc
from app.services.application import get_application_for_user
from app.services.interview import release_device as release_device_svc
from app.services.interview import score_pending
from app.services.job import get_owned_job
from app.services.storage import StorageError, get_storage

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview", response_model=OverviewOut)
def overview(user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    """Recruiter home page: totals across all jobs, recent applications, items needing attention."""
    return svc.recruiter_overview(db, user.id)


@router.get("/jobs/{job_id}/candidates", response_model=list[CandidateRow])
def candidates(
    job_id: uuid.UUID,
    min_score: float | None = Query(default=None, ge=0, le=100),
    max_score: float | None = Query(default=None, ge=0, le=100),
    stage: Stage | None = None,
    decision: Decision | None = None,
    sort: str = Query(default="recent", pattern="^(recent|composite|resume|interview|date|name)$"),
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_owned_job(db, job_id, user)
    return svc.ranked_candidates(
        db,
        job,
        min_score=min_score,
        max_score=max_score,
        stage=stage.value if stage else None,
        decision=decision.value if decision else None,
        sort=sort,
    )


@router.get("/jobs/{job_id}/stats", response_model=JobStatsOut)
def stats(job_id: uuid.UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    return svc.job_stats(db, get_owned_job(db, job_id, user))


@router.get("/applications/{application_id}/detail", response_model=ApplicationDetailOut)
def detail(application_id: uuid.UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    application = get_application_for_user(db, application_id, user)
    if application.interview and any(r.pending for r in application.interview.responses):
        score_pending(db, application.interview)  # answers the AI was too busy to score earlier
    svc.mark_viewed(db, application)  # clears the "New" badge on the dashboard
    return svc.application_detail(application)


@router.patch("/applications/{application_id}/decision", response_model=ApplicationDetailOut)
def decision(
    application_id: uuid.UUID, data: DecisionIn, user: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    application = get_application_for_user(db, application_id, user)
    return svc.application_detail(svc.set_decision(db, application, data.decision, data.notes))


@router.post("/applications/{application_id}/invite", response_model=ApplicationDetailOut)
def invite_to_interview(
    application_id: uuid.UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    """Invite a candidate who was screened out (or could not be screened) to the voice interview anyway."""
    application = get_application_for_user(db, application_id, user)
    return svc.application_detail(svc.manual_invite(db, application))


@router.post("/applications/{application_id}/interview/release-device", response_model=ApplicationDetailOut)
def release_device(application_id: uuid.UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    """Let the candidate continue the interview on a different device or browser."""
    application = get_application_for_user(db, application_id, user)
    if application.interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No interview yet")
    release_device_svc(db, application.interview)
    return svc.application_detail(application)


@router.get("/applications/{application_id}/snapshots/{index}")
def snapshot(
    application_id: uuid.UUID, index: int, user: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    application = get_application_for_user(db, application_id, user)
    snaps = (application.interview.snapshots if application.interview else None) or []
    snap = next((x for x in snaps if x["index"] == index), None)
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found")
    try:
        data = get_storage().load(snap["key"])
    except StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found") from None
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.get("/applications/{application_id}/audio/{question_index}")
def answer_audio(
    application_id: uuid.UUID,
    question_index: int,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    application = get_application_for_user(db, application_id, user)
    session = application.interview
    resp = next((r for r in (session.responses if session else []) if r.question_index == question_index), None)
    if resp is None or not resp.audio_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recording not found")
    try:
        data = get_storage().load(resp.audio_key)
    except StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recording not found") from None
    ext = resp.audio_key.rsplit(".", 1)[-1]
    media = {
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "mp4": "audio/mp4",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
    }.get(ext, "application/octet-stream")
    return Response(content=data, media_type=media, headers={"Cache-Control": "private, no-store"})
