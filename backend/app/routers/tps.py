import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.tps_ir_assist_agent import run_tps_ir_assist
from app.agents.session_store import get_tps_ir_session, save_tps_ir_session
from app.db.models import FormDefinition, FormSubmission, FormVersion, IrForm, SubmissionEvent, TpsIrMain
from app.db.session import get_db
import uuid

from app.schemas.form import (
    IrFormCreate,
    IrFormOut,
    SubmissionDataUpdate,
    TpsFormCandidate,
    TpsFormSearchResponse,
    TpsIrAssistRequest,
    TpsIrAssistResponse,
    TpsIrContextRequest,
    TpsIrOut,
    TpsIrUpdate,
    TpsReleaseOut,
)
from app.vectorstore.store import get_published_form_retriever

router = APIRouter(prefix="/api/tps", tags=["tps"])
logger = logging.getLogger(__name__)


def _record_submission_event(db: Session, submission: FormSubmission, event_type: str, details: dict | None = None) -> None:
    db.add(SubmissionEvent(
        submission_id=submission.id,
        event_type=event_type,
        actor_type="system",
        details=details or {},
    ))


def _serialize_ir_form(ir_number: str, assignment: IrForm, db: Session) -> dict:
    """Enrich an IR form assignment with readable metadata and its submission snapshot."""
    definition = db.query(FormDefinition).filter(FormDefinition.id == assignment.form_id).first()
    version = db.query(FormVersion).filter(FormVersion.id == assignment.form_version_id).first()
    submission = db.query(FormSubmission).filter(
        FormSubmission.ir_id == assignment.ir_id,
        FormSubmission.submission_number == f"SUB-{ir_number}-{assignment.id}",
    ).first()
    events = db.query(SubmissionEvent).filter(
        SubmissionEvent.submission_id == submission.id if submission else False,
    ).order_by(SubmissionEvent.created_at.desc()).all() if submission else []
    return {
        "id": assignment.id,
        "ir_id": assignment.ir_id,
        "form_id": assignment.form_id,
        "form_version_id": assignment.form_version_id,
        "form_title": definition.title if definition else "Assigned form",
        "version_number": version.version_number if version else "",
        "status": assignment.status,
        "required": assignment.required,
        "display_order": assignment.display_order,
        "released_at": assignment.released_at,
        "submission_id": submission.id if submission else None,
        "form_snapshot": submission.form_snapshot if submission else None,
        "submission_data": submission.submission_data if submission else None,
        "event_history": [
            {"event_type": event.event_type, "actor_type": event.actor_type, "created_at": event.created_at, "details": event.details}
            for event in events
        ],
    }


@router.get("/irs", response_model=list[TpsIrOut])
def list_implementation_requests(db: Session = Depends(get_db)):
    """List TPS implementation requests for the first TPS workspace view."""
    return db.query(TpsIrMain).order_by(TpsIrMain.created_at.desc()).all()


@router.get("/irs/{ir_number}", response_model=TpsIrOut)
def get_implementation_request(ir_number: str, db: Session = Depends(get_db)):
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    return ir

@router.put("/irs/{ir_number}", response_model=TpsIrOut)
def update_implementation_request(
    ir_number: str,
    payload: TpsIrUpdate,
    db: Session = Depends(get_db),
):
    """Update editable TPS IR fields using an explicit, LLM-friendly contract."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    for field_name, value in payload.model_dump().items():
        setattr(ir, field_name, value)
    db.commit()
    db.refresh(ir)
    logger.info("PUT /api/tps/irs/%s completed", ir_number)
    return ir


@router.post("/assist/search-forms", response_model=TpsFormSearchResponse)
def search_published_forms(payload: TpsIrAssistRequest, db: Session = Depends(get_db)):
    """Find published form candidates by field names/labels."""
    documents = get_published_form_retriever(k=5).invoke(payload.prompt)
    candidates: list[TpsFormCandidate] = []
    seen: set[str] = set()
    for document in documents:
        version_id = document.metadata.get("version_id")
        if not version_id or version_id in seen:
            continue
        version = db.query(FormVersion).filter(FormVersion.id == uuid.UUID(version_id), FormVersion.status == "published").first()
        if not version:
            continue
        definition = db.query(FormDefinition).filter(FormDefinition.id == version.form_id).first()
        if not definition:
            continue
        seen.add(version_id)
        candidates.append(TpsFormCandidate(
            form_id=definition.id,
            version_id=version.id,
            title=definition.title,
            version_number=version.version_number,
            match_summary="Candidate matched by published field names and labels.",
        ))

    if not candidates:
        return TpsFormSearchResponse(
            status="not_available",
            assistant_message="No suitable published form is available. Please create this form using Form Builder first.",
        )
    return TpsFormSearchResponse(
        status="recommendation",
        forms=candidates,
        assistant_message="I found published form candidates. Would you like to use one of these forms?",
    )


@router.post("/irs/{ir_number}/forms", response_model=IrFormOut)
def assign_form_to_ir(ir_number: str, payload: IrFormCreate, db: Session = Depends(get_db)):
    """Assign a published form version after explicit user confirmation."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    version = db.query(FormVersion).filter(FormVersion.id == payload.form_version_id, FormVersion.form_id == payload.form_id, FormVersion.status == "published").first()
    if not ir or not version:
        raise HTTPException(status_code=404, detail="Implementation request or published form version not found")
    definition = db.query(FormDefinition).filter(FormDefinition.id == payload.form_id).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Form definition not found")

    assignment = IrForm(ir_id=ir.id, form_id=payload.form_id, form_version_id=payload.form_version_id, required=payload.required, display_order=payload.display_order)
    db.add(assignment)
    try:
        db.flush()
        submission = FormSubmission(
            ir_id=ir.id,
            submission_number=f"SUB-{ir_number}-{assignment.id}",
            status="draft",
            form_snapshot={
                "form_id": str(definition.id),
                "version_id": str(version.id),
                "title": definition.title,
                "version_number": version.version_number,
                "layout_tree": version.layout_tree,
            },
            submission_data={},
        )
        db.add(submission)
        db.flush()
        _record_submission_event(db, submission, "assigned")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This form is already assigned to the implementation request") from exc
    db.refresh(assignment)
    return _serialize_ir_form(ir_number, assignment, db)


@router.get("/irs/{ir_number}/forms", response_model=list[IrFormOut])
def list_ir_forms(ir_number: str, db: Session = Depends(get_db)):
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    assignments = db.query(IrForm).filter(IrForm.ir_id == ir.id).order_by(
        IrForm.released_at.desc().nullslast(),
        IrForm.display_order,
        IrForm.created_at,
    ).all()
    return [_serialize_ir_form(ir_number, assignment, db) for assignment in assignments]


@router.delete("/irs/{ir_number}/forms/{ir_form_id}", status_code=204)
def delete_ir_form(ir_number: str, ir_form_id: str, db: Session = Depends(get_db)):
    """Delete an assigned form only while it is still unreleased."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    assignment = db.query(IrForm).filter(IrForm.id == uuid.UUID(ir_form_id), IrForm.ir_id == ir.id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assigned form not found")
    if assignment.status != "assigned":
        raise HTTPException(status_code=409, detail="Only unreleased forms can be deleted")

    submission = db.query(FormSubmission).filter(
        FormSubmission.ir_id == ir.id,
        FormSubmission.submission_number == f"SUB-{ir_number}-{assignment.id}",
    ).first()
    if submission:
        db.delete(submission)
    db.delete(assignment)
    db.commit()


@router.put("/irs/{ir_number}/forms/{ir_form_id}/submission", response_model=IrFormOut)
def save_ir_form_submission(ir_number: str, ir_form_id: str, payload: SubmissionDataUpdate, db: Session = Depends(get_db)):
    """Save the client-filled answers for an assigned form as a draft (does not change release status)."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    assignment = db.query(IrForm).filter(IrForm.id == uuid.UUID(ir_form_id), IrForm.ir_id == ir.id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assigned form not found")
    submission = db.query(FormSubmission).filter(
        FormSubmission.ir_id == ir.id,
        FormSubmission.submission_number == f"SUB-{ir_number}-{assignment.id}",
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found for this assigned form")
    submission.submission_data = payload.submission_data
    _record_submission_event(db, submission, "saved")
    db.commit()
    return _serialize_ir_form(ir_number, assignment, db)


@router.post("/irs/{ir_number}/forms/{ir_form_id}/submit", response_model=TpsReleaseOut)
def submit_ir_form(ir_number: str, ir_form_id: str, db: Session = Depends(get_db)):
    """Submit a released form back after the client completes its Form Review."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    assignment = db.query(IrForm).filter(IrForm.id == uuid.UUID(ir_form_id), IrForm.ir_id == ir.id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assigned form not found")
    if assignment.status != "released":
        raise HTTPException(status_code=409, detail="Only released forms can be submitted back")
    submission = db.query(FormSubmission).filter(
        FormSubmission.ir_id == ir.id,
        FormSubmission.submission_number == f"SUB-{ir_number}-{assignment.id}",
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found for this assigned form")

    assignment.status = "submitted"
    submission.status = "submitted"
    submission.submitted_at = func.now()
    _record_submission_event(db, submission, "submitted")
    db.commit()
    return TpsReleaseOut(ir_form_id=assignment.id, submission_id=submission.id, status=assignment.status)


@router.post("/irs/{ir_number}/forms/{ir_form_id}/release", response_model=TpsReleaseOut)
def release_ir_form(ir_number: str, ir_form_id: str, db: Session = Depends(get_db)):
    """Release an assigned form once and reuse its initial blank submission."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    assignment = db.query(IrForm).filter(IrForm.id == uuid.UUID(ir_form_id), IrForm.ir_id == ir.id if ir else False).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assigned form not found")
    existing = db.query(FormSubmission).filter(
        FormSubmission.ir_id == ir.id,
        FormSubmission.submission_number == f"SUB-{ir_number}-{assignment.id}",
    ).first()
    if assignment.status == "released" and existing:
        return TpsReleaseOut(ir_form_id=assignment.id, submission_id=existing.id, status=assignment.status)

    version = db.query(FormVersion).filter(FormVersion.id == assignment.form_version_id).first()
    definition = db.query(FormDefinition).filter(FormDefinition.id == assignment.form_id).first()
    if not version or not definition:
        raise HTTPException(status_code=404, detail="Published form version not found")
    assignment.status = "released"
    assignment.released_at = func.now()
    if not existing:
        existing = FormSubmission(
            ir_id=ir.id,
            submission_number=f"SUB-{ir_number}-{assignment.id}",
            status="draft",
            form_snapshot={"form_id": str(definition.id), "version_id": str(version.id), "title": definition.title, "version_number": version.version_number, "layout_tree": version.layout_tree},
            submission_data={},
        )
        db.add(existing)
        db.flush()
    _record_submission_event(db, existing, "released")
    db.commit()
    db.refresh(existing)
    return TpsReleaseOut(ir_form_id=assignment.id, submission_id=existing.id, status=assignment.status)


@router.post("/irs/{ir_number}/forms/{ir_form_id}/recall", response_model=TpsReleaseOut)
def recall_ir_form(ir_number: str, ir_form_id: str, db: Session = Depends(get_db)):
    """Recall a released form and return its assignment to draft work."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    assignment = db.query(IrForm).filter(IrForm.id == uuid.UUID(ir_form_id), IrForm.ir_id == ir.id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assigned form not found")
    submission = db.query(FormSubmission).filter(
        FormSubmission.ir_id == ir.id,
        FormSubmission.submission_number == f"SUB-{ir_number}-{assignment.id}",
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found for this assigned form")

    assignment.status = "assigned"
    assignment.released_at = None
    submission.status = "draft"
    submission.submitted_at = None
    _record_submission_event(db, submission, "recalled")
    db.commit()
    return TpsReleaseOut(ir_form_id=assignment.id, submission_id=submission.id, status=assignment.status)


@router.post("/irs/{ir_number}/assist", response_model=TpsIrAssistResponse)
def assist_implementation_request(
    ir_number: str,
    payload: TpsIrAssistRequest,
    db: Session = Depends(get_db),
):
    """Answer a question using stored IR context and the session conversation history."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")

    session = get_tps_ir_session(payload.session_id)
    if payload.ir_context is not None:
        session["ir_context"] = payload.ir_context.model_dump()
    if not session["ir_context"]:
        raise HTTPException(status_code=409, detail="Load IR context before asking a question")

    result = run_tps_ir_assist(payload.prompt, session["messages"], session["ir_context"])
    session["messages"] = result["messages"]
    pending_form = (
        result.get("published_forms", [None])[0]
        if result.get("published_forms") and not result.get("show_all_forms")
        else None
    )
    session["pending_form"] = pending_form
    save_tps_ir_session(payload.session_id, session)
    return TpsIrAssistResponse(
        assistant_message=result["assistant_message"],
        published_forms=result.get("published_forms", []),
        pending_form=pending_form,
    )


@router.post("/irs/{ir_number}/assist/context")
def load_ir_assistant_context(
    ir_number: str,
    payload: TpsIrContextRequest,
    db: Session = Depends(get_db),
):
    """Load or replace the IR context for a TPS IR Assist session."""
    ir = db.query(TpsIrMain).filter(TpsIrMain.ir_number == ir_number).first()
    if not ir:
        raise HTTPException(status_code=404, detail="Implementation request not found")
    if payload.ir_context.ir_number != ir_number:
        raise HTTPException(status_code=422, detail="IR context does not match the requested IR")

    session = get_tps_ir_session(payload.session_id)
    session["ir_context"] = payload.ir_context.model_dump()
    session["messages"] = []
    session["pending_form"] = None
    save_tps_ir_session(payload.session_id, session)
    return {"status": "context_loaded", "session_id": payload.session_id, "ir_number": ir_number}
