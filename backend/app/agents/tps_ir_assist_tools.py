"""Database-backed submitted-form context loader for TPS IR Assist."""

from typing import Any
import logging

from sqlalchemy.orm import Session

from app.db.models import FormSubmission

logger = logging.getLogger(__name__)


def load_latest_submitted_form(db: Session, ir_id: Any) -> dict[str, Any] | None:
    """Load only the most recently submitted response for an implementation request."""
    logger.info("IR Assist tool load_latest_submitted_form started ir_id=%s", ir_id)
    submission = (
        db.query(FormSubmission)
        .filter(FormSubmission.ir_id == ir_id, FormSubmission.status == "submitted")
        .order_by(FormSubmission.submitted_at.desc().nullslast(), FormSubmission.created_at.desc())
        .first()
    )
    if not submission:
        logger.info("IR Assist tool load_latest_submitted_form found no submitted row ir_id=%s", ir_id)
        return None

    snapshot = submission.form_snapshot or {}
    logger.info(
        "IR Assist tool load_latest_submitted_form selected submission_id=%s status=%s submitted_at=%s",
        submission.id,
        submission.status,
        submission.submitted_at,
    )
    return {
        "submission_id": str(submission.id),
        "submission_number": submission.submission_number,
        "status": submission.status,
        "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "form_snapshot": snapshot,
        "submission_data": submission.submission_data or {},
        "form_title": snapshot.get("title", "Submitted form"),
        "version_id": snapshot.get("version_id"),
        "version_number": snapshot.get("version_number"),
    }
