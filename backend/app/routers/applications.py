import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user, require_candidate, require_recruiter
from app.core.limiter import limiter
from app.database import get_db
from app.models import User
from app.models.enums import Stage
from app.schemas.application import ApplicationCreatedOut, MyApplicationOut
from app.services import application as svc
from app.services import resume as resume_svc
from app.services.job import get_job_for_user
from app.services.storage import StorageError, get_storage

router = APIRouter(tags=["applications"])


def _screen_later(background: BackgroundTasks, application_id: uuid.UUID) -> None:
    """Normally screening runs after the response. On serverless hosting it must finish inside the request."""
    if settings.serverless:
        resume_svc.screen(application_id)
    else:
        background.add_task(resume_svc.screen, application_id)


@router.post("/jobs/{job_id}/apply", response_model=ApplicationCreatedOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def apply(
    request: Request,
    job_id: uuid.UUID,
    background: BackgroundTasks,
    resume: UploadFile | None = File(default=None),
    answers: str = Form(default="{}", max_length=50_000),
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    """Multipart form: `answers`, a JSON object {question_id: answer} for the job's form, and optionally a PDF
    `resume` for this job only (otherwise the profile's resume is used). The profile must be complete. On
    serverless hosting the answer already says whether the candidate was selected for the interview, and why not."""
    job = get_job_for_user(db, job_id, user)
    data = await svc.read_limited(resume, svc.MAX_RESUME_BYTES) if resume is not None else None
    application = svc.apply(db, job, user, resume, data, svc.parse_answers(answers))
    if settings.serverless:
        await run_in_threadpool(resume_svc.screen, application.id)
        db.expire_all()  # screening used its own session; read the result it saved
    else:
        background.add_task(resume_svc.screen, application.id)
    return ApplicationCreatedOut(
        id=application.id,
        job_id=job.id,
        stage=application.stage,
        created_at=application.created_at,
        status_label=svc.CANDIDATE_VIEW[Stage(application.stage)][0],
        reason=svc.candidate_reason(application),
    )


@router.get("/applications/mine", response_model=list[MyApplicationOut])
def my_applications(user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    return svc.my_applications(db, user)


@router.get("/applications/{application_id}/resume")
def download_resume(application_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    application = svc.get_application_for_user(db, application_id, user)
    if application.resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    try:
        data = get_storage().load(application.resume.file_key)
    except StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume file not found") from None
    filename = application.resume.original_filename.replace('"', "")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.post("/applications/{application_id}/rescreen", status_code=status.HTTP_202_ACCEPTED)
def rescreen(
    application_id: uuid.UUID,
    background: BackgroundTasks,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    application = svc.get_application_for_user(db, application_id, user)
    if application.stage != Stage.SCREENING_FAILED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only applications whose screening failed can be re-screened")
    _screen_later(background, application.id)
    return {"detail": "Screening restarted"}
