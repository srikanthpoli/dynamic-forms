import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.field_builder_agent import run_field_builder
from app.agents.session_store import get_session, kill_session, save_session
from app.db.models import FieldTemplate
from app.db.session import get_db
from app.schemas.field import (
    FieldDraftResponse,
    FieldGenerateRequest,
    FieldOverrideRequest,
    FieldPublishRequest,
    FieldTemplateOut,
)

router = APIRouter(prefix="/api/fields", tags=["fields"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=FieldDraftResponse)
def generate_field(payload: FieldGenerateRequest):
    """History-aware draft generation. Call again with the same session_id to
    refine the draft (e.g. "make it required", "add a max length of 50").

    In Swagger, reuse the same session_id for each refinement request.
    """
    logger.info("POST /api/fields/generate started session_id=%s", payload.session_id)
    session = get_session(payload.session_id)
    try:
        result = run_field_builder(payload.prompt, session["messages"], payload.field_context)
    except Exception:
        logger.exception("POST /api/fields/generate failed session_id=%s", payload.session_id)
        raise

    session["messages"] = result["messages"]
    session["draft"] = result["draft"]
    save_session(payload.session_id, session)

    logger.info("POST /api/fields/generate completed session_id=%s", payload.session_id)
    draft = result["draft"]
    return FieldDraftResponse(
        name=draft.get("name") or draft.get("field_id", "generated_field"),
        label=draft["label"],
        field_type=draft["field_type"],
        angular_config=draft.get("angular_config", {}),
        validation_rules=draft["validation_rules"],
        api_config=draft.get("api_config"),
        validation_messages=draft["validation_messages"],
        assistant_message=result["assistant_message"],
    )


@router.post("/publish", response_model=FieldTemplateOut)
def publish_field(payload: FieldPublishRequest, db: Session = Depends(get_db)):
    """Persist a complete field template independently of any generation session."""
    logger.info("POST /api/fields/publish started name=%s", payload.name)
    existing = db.query(FieldTemplate).filter(FieldTemplate.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="A field template with this name already exists")

    template = FieldTemplate(
        name=payload.name,
        label=payload.label,
        field_type=payload.field_type,
        angular_config=payload.angular_config,
        validation_rules=payload.validation_rules,
        api_config=payload.api_config,
        validation_messages=payload.validation_messages,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    logger.info("POST /api/fields/publish completed template_id=%s", template.id)
    return template


@router.get("/", response_model=list[FieldTemplateOut])
def list_field_templates(db: Session = Depends(get_db)):
    return db.query(FieldTemplate).all()


@router.put("/{field_id}", response_model=FieldTemplateOut)
def override_field(field_id: UUID, payload: FieldOverrideRequest, db: Session = Depends(get_db)):
    """Replace a published field definition with the supplied values."""
    logger.info("PUT /api/fields/%s started", field_id)
    template = db.query(FieldTemplate).filter(FieldTemplate.id == field_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Field template not found")

    duplicate = (
        db.query(FieldTemplate)
        .filter(FieldTemplate.name == payload.name, FieldTemplate.id != field_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A field template with this name already exists")

    template.name = payload.name
    template.label = payload.label
    template.field_type = payload.field_type
    template.angular_config = payload.angular_config
    template.validation_rules = payload.validation_rules
    template.validation_messages = payload.validation_messages
    template.api_config = payload.api_config
    db.commit()
    db.refresh(template)
    logger.info("PUT /api/fields/%s completed", field_id)
    return template


@router.delete("/{field_id}")
def delete_field(field_id: UUID, db: Session = Depends(get_db)):
    """Delete a field template from the published library."""
    logger.info("DELETE /api/fields/%s started", field_id)
    template = db.query(FieldTemplate).filter(FieldTemplate.id == field_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Field template not found")

    db.delete(template)
    db.commit()
    logger.info("DELETE /api/fields/%s completed", field_id)
    return {"status": "deleted", "field_id": str(field_id)}


@router.delete("/sessions/{session_id}")
def kill_field_session(session_id: str):
    """Clear a session's in-memory conversation history and pending draft."""
    existed = kill_session(session_id)
    return {"status": "cleared" if existed else "not_found"}
