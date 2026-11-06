"""Writes rows to the insert-only ai_audit_log. There is deliberately NO update or delete function here."""

import logging
import uuid

from sqlalchemy.orm import Session

from app.models import AIAuditLog

log = logging.getLogger(__name__)


def write_audit(
    db: Session, *, application_id: uuid.UUID | None, kind: str, model: str, input_text: str, raw_output: str | None
) -> None:
    """Insert one audit row in its OWN session/transaction so it is kept even if the caller rolls back."""
    try:
        with Session(bind=db.get_bind()) as audit_db:
            audit_db.add(
                AIAuditLog(
                    application_id=application_id, kind=kind, model=model, input=input_text, raw_output=raw_output
                )
            )
            audit_db.commit()
    except Exception as exc:  # auditing must never crash the main flow
        log.error("Could not write AI audit log: %s", exc)
