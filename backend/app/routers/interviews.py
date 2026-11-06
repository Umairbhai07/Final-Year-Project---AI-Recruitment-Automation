import uuid

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import require_candidate
from app.database import get_db
from app.models import User
from app.schemas.interview import AnswerOut, EventsIn, EventsOut, InterviewStateOut, IssueIn, SkipIn
from app.services import interview as svc
from app.services.application import read_limited

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.get("/{session_id}", response_model=InterviewStateOut)
def get_interview(session_id: uuid.UUID, user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    return svc.state(svc.get_session_for_candidate(db, session_id, user))


Device = Header(default=None, alias="X-Interview-Device", max_length=100)


@router.post("/{session_id}/start", response_model=InterviewStateOut)
def start(
    session_id: uuid.UUID,
    device: str | None = Device,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    return svc.start(db, svc.get_session_for_candidate(db, session_id, user), device)


def _session(db: Session, session_id: uuid.UUID, user: User, device: str | None):
    session = svc.get_session_for_candidate(db, session_id, user)
    svc.check_device(db, session, device)
    return session


@router.post("/{session_id}/answer", response_model=AnswerOut)
async def answer(
    session_id: uuid.UUID,
    question_index: int = Form(...),
    audio: UploadFile = File(...),
    attention: float | None = Form(None, ge=0, le=100),
    device: str | None = Device,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    session = _session(db, session_id, user, device)
    data = await read_limited(audio, svc.MAX_AUDIO_BYTES)
    return svc.submit_answer(db, session, question_index, audio, data, attention)


@router.post("/{session_id}/report-issue", status_code=status.HTTP_204_NO_CONTENT)
def report_issue(
    session_id: uuid.UUID, data: IssueIn, user: User = Depends(require_candidate), db: Session = Depends(get_db)
):  # allowed from any device: a candidate locked out must still be able to tell the recruiter
    svc.report_issue(db, svc.get_session_for_candidate(db, session_id, user), data.text)


@router.post("/{session_id}/snapshot")
async def snapshot(
    session_id: uuid.UUID,
    image: UploadFile = File(...),
    reason: str = Form(..., max_length=30),
    question_index: int | None = Form(default=None, ge=0, le=50),
    device: str | None = Device,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    """A small webcam photo for the recruiter (taken with the candidate's consent during the interview)."""
    session = _session(db, session_id, user, device)
    data = await read_limited(image, svc.MAX_SNAPSHOT_BYTES)
    return svc.add_snapshot(db, session, data, reason, question_index)


@router.post("/{session_id}/skip", response_model=AnswerOut)
def skip(
    session_id: uuid.UUID,
    data: SkipIn,
    device: str | None = Device,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    """Time ran out with nothing recorded: the question scores 0 and the interview moves on."""
    return svc.skip_question(db, _session(db, session_id, user, device), data.question_index)


@router.post("/{session_id}/events", response_model=EventsOut)
def events(
    session_id: uuid.UUID,
    data: EventsIn,
    device: str | None = Device,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    """Lockdown events from the browser (left full screen, switched tab...). Ends the interview at the limit."""
    session = _session(db, session_id, user, device)
    return svc.record_events(db, session, [e.model_dump() for e in data.events])
