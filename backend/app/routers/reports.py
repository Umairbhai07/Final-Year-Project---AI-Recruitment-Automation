import re
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import require_recruiter
from app.database import get_db
from app.models import User
from app.services import report
from app.services.dashboard import ranked_candidates
from app.services.job import get_owned_job

router = APIRouter(tags=["reports"])


@router.get("/jobs/{job_id}/export")
def export(
    job_id: uuid.UUID,
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    only_shortlisted: bool = False,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_owned_job(db, job_id, user)
    rows = ranked_candidates(db, job, only_shortlisted=only_shortlisted)
    slug = re.sub(r"[^a-z0-9]+", "-", job.title.lower()).strip("-") or "job"
    if format == "pdf":
        return Response(
            report.to_pdf(job, rows, only_shortlisted),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{slug}-candidates.pdf"'},
        )
    return Response(
        report.to_csv(job, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-candidates.csv"'},
    )
