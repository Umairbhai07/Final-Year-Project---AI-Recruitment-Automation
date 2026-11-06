import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_recruiter
from app.database import get_db
from app.models import Application, Job, User
from app.models.enums import Role
from app.schemas.job import JobCreate, JobMineOut, JobOut, JobStatusIn, JobUpdate
from app.services import job as svc
from app.services import profile as profile_svc

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _out(job: Job, applied_ids: set | None = None, viewer: User | None = None) -> JobOut:
    out = JobOut.model_validate(job)
    out.company = job.recruiter.full_name if job.recruiter else None
    if applied_ids is not None:
        out.has_applied = job.id in applied_ids
    if viewer is not None and viewer.role == Role.CANDIDATE:
        out.eligibility = profile_svc.eligibility(job, viewer.profile)
        out.blocked_applications = None
        # Candidates see the questions, not which answers pass (so they can't just give the passing answer).
        out.application_form = [
            q.model_copy(update={"accept": [], "must_min": None, "must_max": None}) for q in out.application_form or []
        ]
    return out


def _applied_job_ids(db: Session, user: User) -> set | None:
    if user.role != Role.CANDIDATE:
        return None
    return set(db.scalars(select(Application.job_id).where(Application.candidate_id == user.id)))


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(data: JobCreate, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    return _out(svc.create_job(db, user, data))


@router.get("", response_model=list[JobOut])
def list_jobs(
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Active jobs open for applications. Search by title or skill with ?q=."""
    applied = _applied_job_ids(db, user)
    return [_out(j, applied, user) for j in svc.list_active_jobs(db, q)]


@router.get("/mine", response_model=list[JobMineOut])
def my_jobs(user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    out = []
    for row in svc.list_my_jobs(db, user):
        item = JobMineOut.model_validate(row["job"])
        item.applicant_count, item.evaluated_count, item.avg_score = (
            row["applicant_count"],
            row["evaluated_count"],
            row["avg_score"],
        )
        out.append(item)
    return out


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(svc.get_job_for_user(db, job_id, user), _applied_job_ids(db, user), user)


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: uuid.UUID, data: JobUpdate, user: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    return _out(svc.update_job(db, svc.get_owned_job(db, job_id, user), data))


@router.patch("/{job_id}/status", response_model=JobOut)
def change_status(
    job_id: uuid.UUID, data: JobStatusIn, user: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    return _out(svc.change_status(db, svc.get_owned_job(db, job_id, user), data.status))
