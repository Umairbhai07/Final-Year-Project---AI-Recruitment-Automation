import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import require_candidate, require_recruiter
from app.core.limiter import limiter
from app.database import get_db
from app.models import User
from app.schemas.profile import Eligibility, ProfileIn, ProfileOut
from app.services import profile as svc
from app.services.application import read_limited
from app.services.dashboard import last_activity
from app.services.job import get_job_for_user

router = APIRouter(tags=["profile"])

IMAGE_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


@router.get("/profile/me", response_model=ProfileOut)
def my_profile(user: User = Depends(require_candidate)):
    return svc.to_out(user)


@router.put("/profile/me", response_model=ProfileOut)
def save_profile(data: ProfileIn, user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    return svc.to_out(svc.update(db, user, data))


@router.post("/profile/me/photo", response_model=ProfileOut)
@limiter.limit("20/minute")
async def upload_photo(
    request: Request,
    image: UploadFile = File(...),
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    data = await read_limited(image, svc.MAX_PHOTO_BYTES)
    return svc.to_out(svc.save_photo(db, user, data))


@router.post("/profile/me/resume", response_model=ProfileOut)
@limiter.limit("20/minute")
async def upload_resume(
    request: Request,
    resume: UploadFile = File(...),
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    from app.services.application import MAX_RESUME_BYTES

    data = await read_limited(resume, MAX_RESUME_BYTES)
    return svc.to_out(svc.save_resume(db, user, resume, data))


def _pdf(data: bytes, filename: str | None) -> Response:
    name = (filename or "resume.pdf").replace('"', "")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "private, no-store"},
    )


@router.get("/profile/me/resume")
def my_resume(user: User = Depends(require_candidate)):
    p = user.profile
    return _pdf(svc.load_file(p.resume_key if p else None), p.resume_filename if p else None)


@router.get("/photos/{user_id}")
def photo(
    user_id: uuid.UUID, exp: int = Query(...), sig: str = Query(..., max_length=64), db: Session = Depends(get_db)
):
    """Profile photo behind a signed, expiring link (so it works in <img src> without a login header)."""
    user = db.get(User, user_id)
    key = user.profile.photo_key if user and user.profile else None
    if not key or not svc.check_photo_signature(user_id, key, exp, sig):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    ext = key.rsplit(".", 1)[-1]
    return Response(
        content=svc.load_file(key),
        media_type=IMAGE_TYPES.get(ext, "image/jpeg"),
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/jobs/{job_id}/eligibility", response_model=Eligibility)
def job_eligibility(job_id: uuid.UUID, user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    return svc.eligibility(get_job_for_user(db, job_id, user), user.profile)


@router.get("/candidates/{candidate_id}")
def candidate_profile(candidate_id: uuid.UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    """A candidate's profile and the jobs THIS recruiter received applications for (never other companies')."""
    candidate, apps = svc.candidate_for_recruiter(db, candidate_id, user)
    applications = []
    for a in apps:
        ev = a.evaluation
        when, what = last_activity(a)
        applications.append(
            {
                "application_id": str(a.id),
                "job_id": str(a.job_id),
                "job_title": a.job.title,
                "job_status": a.job.status,
                "applied_at": a.created_at,
                "stage": a.stage,
                "decision": a.recruiter_decision,
                "composite_score": ev.composite_score if ev else None,
                "incomplete": ev.incomplete if ev else True,
                "last_activity": what,
                "last_activity_at": when,
                "mismatches": a.mismatches or [],
            }
        )
    out = svc.to_out(candidate)
    out.pop("missing", None)
    return {"profile": out, "member_since": candidate.created_at, "applications": applications}


@router.get("/candidates/{candidate_id}/resume")
def candidate_resume(candidate_id: uuid.UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    candidate, _ = svc.candidate_for_recruiter(db, candidate_id, user)
    p = candidate.profile
    return _pdf(svc.load_file(p.resume_key if p else None), p.resume_filename if p else None)
