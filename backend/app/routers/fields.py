import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
from app.vectorstore.store import delete_published_field, upsert_published_field

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
    except ValueError as exc:
        logger.exception("POST /api/fields/generate capability references unavailable")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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


@router.post("/generate/stream")
def generate_field_stream(payload: FieldGenerateRequest):
    """Stream progress events, then return the final validated field result."""
    def events():
        yield _sse_event("status", {"message": "Searching Angular Material capability references..."})
        session = get_session(payload.session_id)
        try:
            yield _sse_event("status", {"message": "Generating the field definition..."})
            result = run_field_builder(payload.prompt, session["messages"], payload.field_context)
            session["messages"] = result["messages"]
            session["draft"] = result["draft"]
            save_session(payload.session_id, session)
            draft = result["draft"]
            response = FieldDraftResponse(
                name=draft.get("name") or draft.get("field_id", "generated_field"),
                label=draft["label"],
                field_type=draft["field_type"],
                angular_config=draft.get("angular_config", {}),
                validation_rules=draft["validation_rules"],
                api_config=draft.get("api_config"),
                validation_messages=draft["validation_messages"],
                assistant_message=result["assistant_message"],
            )
            yield _sse_event("complete", response.model_dump())
        except ValueError as exc:
            yield _sse_event("error", {"message": str(exc)})
        except Exception:
            logger.exception("Streaming field generation failed session_id=%s", payload.session_id)
            yield _sse_event("error", {"message": "The Field Builder could not complete this request."})

    return StreamingResponse(events(), media_type="text/event-stream")


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


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
    try:
        upsert_published_field(template)
    except Exception:
        logger.exception("Published field saved but semantic index update failed field_id=%s", template.id)
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
    try:
        upsert_published_field(template)
    except Exception:
        logger.exception("Updated field saved but semantic index update failed field_id=%s", template.id)
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
    try:
        delete_published_field(str(field_id))
    except Exception:
        logger.exception("Field deleted but semantic index update failed field_id=%s", field_id)
    logger.info("DELETE /api/fields/%s completed", field_id)
    return {"status": "deleted", "field_id": str(field_id)}


@router.delete("/sessions/{session_id}")
def kill_field_session(session_id: str):
    """Clear a session's in-memory conversation history and pending draft."""
    existed = kill_session(session_id)
    return {"status": "cleared" if existed else "not_found"}
