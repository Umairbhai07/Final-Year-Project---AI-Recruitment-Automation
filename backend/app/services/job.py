"""Job postings: create, edit, status transitions (closing archives applications), visibility rules."""

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Application, EvaluationScore, Job, User
from app.models.enums import JobStatus, Role, Stage
from app.schemas.job import JobCreate, JobUpdate

# Allowed job status transitions. CLOSED is final.
JOB_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.ACTIVE: {JobStatus.PAUSED, JobStatus.CLOSED},
    JobStatus.PAUSED: {JobStatus.ACTIVE, JobStatus.CLOSED},
    JobStatus.CLOSED: set(),
}


def create_job(db: Session, recruiter: User, data: JobCreate) -> Job:
    from app.services.auth import require_verified

    require_verified(recruiter)
    job = Job(recruiter_id=recruiter.id, **data.model_dump(mode="python"))
    job.education_level = data.education_level.value
    db.add(job)
    db.commit()
    return job


def is_open_for_applications(job: Job) -> bool:
    return job.status == JobStatus.ACTIVE and (job.deadline is None or job.deadline >= date.today())


def get_job_for_user(db: Session, job_id: uuid.UUID, user: User) -> Job:
    """Recruiters see only their own jobs; candidates see only active jobs. Otherwise 404."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if user.role == Role.RECRUITER and job.recruiter_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if user.role == Role.CANDIDATE and job.status != JobStatus.ACTIVE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def get_owned_job(db: Session, job_id: uuid.UUID, recruiter: User) -> Job:
    job = db.get(Job, job_id)
    if job is None or job.recruiter_id != recruiter.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def list_active_jobs(db: Session, q: str | None = None) -> list[Job]:
    """Active jobs whose deadline has not passed. Search matches title or any skill (case-insensitive)."""
    stmt = select(Job).where(Job.status == JobStatus.ACTIVE, or_(Job.deadline.is_(None), Job.deadline >= date.today()))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(Job.title).like(like), func.lower(cast(Job.required_skills, String)).like(like))
        )
    return list(db.scalars(stmt.order_by(Job.created_at.desc())))


def list_my_jobs(db: Session, recruiter: User) -> list[dict]:
    jobs = list(db.scalars(select(Job).where(Job.recruiter_id == recruiter.id).order_by(Job.created_at.desc())))
    if not jobs:
        return []
    ids = [j.id for j in jobs]
    counts = dict(
        db.execute(
            select(Application.job_id, func.count()).where(Application.job_id.in_(ids)).group_by(Application.job_id)
        ).all()
    )
    evaluated = dict(
        db.execute(
            select(Application.job_id, func.count())
            .where(Application.job_id.in_(ids), Application.stage == Stage.EVALUATED)
            .group_by(Application.job_id)
        ).all()
    )
    avgs = dict(
        db.execute(
            select(Application.job_id, func.avg(EvaluationScore.composite_score))
            .join(EvaluationScore, EvaluationScore.application_id == Application.id)
            .where(Application.job_id.in_(ids))
            .group_by(Application.job_id)
        ).all()
    )
    out = []
    for j in jobs:
        avg = avgs.get(j.id)
        out.append(
            {
                "job": j,
                "applicant_count": counts.get(j.id, 0),
                "evaluated_count": evaluated.get(j.id, 0),
                "avg_score": round(float(avg), 1) if avg is not None else None,
            }
        )
    return out


def update_job(db: Session, job: Job, data: JobUpdate) -> Job:
    if job.status == JobStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Closed jobs cannot be edited")
    changes = data.model_dump(exclude_unset=True, mode="python")
    for field, value in changes.items():
        if field not in ("deadline", "min_cgpa") and value is None:
            continue
        setattr(job, field, value.value if hasattr(value, "value") else value)
    db.commit()
    return job


def change_status(db: Session, job: Job, new_status: JobStatus) -> Job:
    if new_status == job.status:
        return job
    if new_status not in JOB_TRANSITIONS[JobStatus(job.status)]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Cannot change job status from {job.status} to {new_status.value}"
        )
    job.status = new_status.value
    if new_status == JobStatus.CLOSED:
        db.execute(update(Application).where(Application.job_id == job.id).values(archived=True))
    db.commit()
    return job
