import logging

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.form_builder_agent import run_form_builder
from app.agents.session_store import get_form_session, kill_form_session, save_form_session
from app.db.models import FieldTemplate, FormDefinition, FormSubmission, FormVersion
from app.db.session import get_db
from app.schemas.form import (
    FormBuildRequest,
    FormBuildResponse,
    FormDefinitionCreate,
    FormDefinitionOut,
    FormDefinitionUpdate,
    FormSubmissionCreate,
    FormSubmissionOut,
    FormVersionOut,
    PublishedFormOut,
    FormDefinitionVersionCreate,
    FormDefinitionVersionUpdate,
    FormVersionCreate,
)
from app.vectorstore.store import delete_published_form, refresh_published_forms_index, upsert_published_form

router = APIRouter(prefix="/api/forms", tags=["forms"])
logger = logging.getLogger(__name__)


def _field_template_json(template: FieldTemplate) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "label": template.label,
        "field_type": template.field_type,
        "angular_config": template.angular_config,
        "validation_rules": template.validation_rules,
        "validation_messages": template.validation_messages,
        "api_config": template.api_config,
    }


def _enrich_layout_tree(layout_tree: list[dict], db: Session) -> list[dict]:
    field_ids = {node.get("field_id") for node in layout_tree if node.get("field_id") and not node.get("field")}
    if not field_ids:
        return layout_tree

    templates = db.query(FieldTemplate).filter(FieldTemplate.id.in_(field_ids)).all()
    templates_by_id = {str(template.id): template for template in templates}
    enriched = []
    for node in layout_tree:
        if node.get("field"):
            enriched.append(node)
            continue
        field_id = node.get("field_id")
        enriched.append({
            **node,
            "field": _field_template_json(templates_by_id[field_id])
            if field_id in templates_by_id else None,
        })
    return enriched


def _snapshot_layout_tree(layout_tree: list[dict], db: Session) -> list[dict]:
    """Store each form node with the complete field definition used at save time."""
    field_ids = {node.get("field_id") for node in layout_tree if node.get("field_id") and not node.get("field")}
    templates = db.query(FieldTemplate).filter(FieldTemplate.id.in_(field_ids)).all() if field_ids else []
    templates_by_id = {str(template.id): template for template in templates}
    snapshots = []
    for node in layout_tree:
        field = node.get("field")
        if not field and node.get("field_id") in templates_by_id:
            field = _field_template_json(templates_by_id[node["field_id"]])
        if not field:
            raise HTTPException(status_code=422, detail="Every form field must include a complete field definition")
        snapshots.append({
            "order": node.get("order", len(snapshots)),
            "column_span": node.get("column_span"),
            "field": field,
        })
    return snapshots


def _agent_layout_tree(layout_tree: list[dict]) -> list[dict]:
    """Add temporary field IDs for the layout agent without persisting them."""
    return [
        {
            **node,
            "field_id": node.get("field_id") or (node.get("field") or {}).get("id"),
        }
        for node in layout_tree
    ]


def _published_form_result(version: FormVersion, definition: FormDefinition, db: Session) -> dict:
    return {
        "form_id": definition.id,
        "title": definition.title,
        "description": definition.description,
        "version_id": version.id,
        "version_number": version.version_number,
        "layout_tree": _enrich_layout_tree(version.layout_tree, db),
    }


_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _next_version_number(db: Session, form_uuid: uuid.UUID, bump: str) -> str:
    """Compute the next semantic version for a form (e.g. 1.0.1, 1.1.0, 2.0.0)."""
    versions = db.query(FormVersion.version_number).filter(FormVersion.form_id == form_uuid).all()
    latest = (1, 0, 0)
    found_any = False
    for (version_number,) in versions:
        match = _VERSION_PATTERN.match(version_number or "")
        if not match:
            continue
        parts = tuple(int(part) for part in match.groups())
        if not found_any or parts > latest:
            latest = parts
            found_any = True

    major, minor, patch = latest
    if not found_any:
        return "1.0.0"
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


@router.post("/definitions", response_model=FormDefinitionOut)
def create_form_definition(payload: FormDefinitionCreate, db: Session = Depends(get_db)):
    """Create the persisted form metadata used by form version endpoints."""
    logger.info("POST /api/forms/definitions started title=%s", payload.title)
    existing = db.query(FormDefinition).filter(FormDefinition.title == payload.title).first()
    if existing:
        raise HTTPException(status_code=409, detail="A form with this name already exists")

    definition = FormDefinition(title=payload.title, description=payload.description)
    db.add(definition)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A form with this name already exists") from exc
    db.refresh(definition)
    logger.info("POST /api/forms/definitions completed form_id=%s", definition.id)
    return {
        "id": str(definition.id),
        "title": definition.title,
        "description": definition.description,
    }


@router.get("/definitions", response_model=list[FormDefinitionOut])
def list_form_definitions(db: Session = Depends(get_db)):
    return db.query(FormDefinition).order_by(FormDefinition.created_at.desc()).all()


@router.get("/definitions/{form_id}", response_model=FormDefinitionOut)
def get_form_definition(form_id: str, db: Session = Depends(get_db)):
    definition = db.query(FormDefinition).filter(FormDefinition.id == uuid.UUID(form_id)).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Form definition not found")
    return definition


@router.put("/definitions/{form_id}", response_model=FormDefinitionOut)
def update_form_definition(form_id: str, payload: FormDefinitionUpdate, db: Session = Depends(get_db)):
    definition = db.query(FormDefinition).filter(FormDefinition.id == uuid.UUID(form_id)).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Form definition not found")

    duplicate = (
        db.query(FormDefinition)
        .filter(FormDefinition.title == payload.title, FormDefinition.id != definition.id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A form with this name already exists")

    definition.title = payload.title
    definition.description = payload.description
    db.commit()
    db.refresh(definition)
    refresh_published_forms_index(db)
    return definition


@router.get("/published", response_model=list[PublishedFormOut])
def list_published_forms(db: Session = Depends(get_db)):
    """Return every published form version with its form metadata and layout."""
    rows = (
        db.query(FormVersion, FormDefinition)
        .join(FormDefinition, FormDefinition.id == FormVersion.form_id)
        .filter(FormVersion.status == "published")
        .order_by(FormVersion.created_at.desc())
        .all()
    )
    logger.info("GET /api/forms/published returned forms=%d", len(rows))
    return [_published_form_result(version, definition, db) for version, definition in rows]


@router.get("/{form_id}/published", response_model=list[PublishedFormOut])
def list_published_versions(form_id: str, db: Session = Depends(get_db)):
    """Return published versions for one form definition."""
    try:
        form_uuid = uuid.UUID(form_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="form_id must be a valid UUID") from exc

    rows = (
        db.query(FormVersion, FormDefinition)
        .join(FormDefinition, FormDefinition.id == FormVersion.form_id)
        .filter(FormVersion.form_id == form_uuid, FormVersion.status == "published")
        .order_by(FormVersion.created_at.desc())
        .all()
    )
    if not rows:
        exists = db.query(FormDefinition.id).filter(FormDefinition.id == form_uuid).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Form definition not found")
    logger.info("GET /api/forms/%s/published returned versions=%d", form_id, len(rows))
    return [_published_form_result(version, definition, db) for version, definition in rows]


@router.post("/build", response_model=FormBuildResponse)
def build_form(payload: FormBuildRequest, db: Session = Depends(get_db)):
    """Form Builder Agent: assemble a layout from already-published field templates.

    Use a field_id returned by GET /api/fields/ when saving a form version.
    """
    logger.info("POST /api/forms/build started session_id=%s", payload.session_id)
    session = get_form_session(payload.session_id)
    if payload.form_context:
        session["form_definition"] = {
            "title": payload.form_context.get("title", "Untitled Form"),
            "description": payload.form_context.get("description"),
            "layout_tree": payload.form_context.get("layout_tree", []),
        }
        session["layout_tree"] = session["form_definition"]["layout_tree"]
    try:
        result = run_form_builder(
            payload.prompt,
            db,
            session["messages"],
            _agent_layout_tree(session["layout_tree"]),
            session["form_definition"],
        )
    except Exception:
        logger.exception("POST /api/forms/build failed session_id=%s", payload.session_id)
        raise
    session["messages"] = result["messages"]
    session["layout_tree"] = result["layout_tree"]
    form_definition = result.get("form_definition") or session["form_definition"]
    form_definition.setdefault("title", "Untitled Form")
    form_definition.setdefault("description", None)
    form_definition.setdefault("layout_tree", session["layout_tree"])
    session["form_definition"] = form_definition
    save_form_session(payload.session_id, session)
    logger.info(
        "POST /api/forms/build completed session_id=%s layout_nodes=%d",
        payload.session_id,
        len(session["layout_tree"]),
    )
    response_definition = {
        **form_definition,
        "layout_tree": _enrich_layout_tree(form_definition["layout_tree"], db),
    }
    return FormBuildResponse(
        session_id=payload.session_id,
        form_definition=response_definition,
        assistant_message=result.get("assistant_message"),
    )


@router.delete("/sessions/{session_id}")
def kill_form_builder_session(session_id: str):
    """Clear a form builder session's conversation history and layout."""
    existed = kill_form_session(session_id)
    return {"status": "cleared" if existed else "not_found"}


@router.get("/{form_id}/versions", response_model=list[FormVersionOut])
def list_form_versions(form_id: str, db: Session = Depends(get_db)):
    form_uuid = uuid.UUID(form_id)
    if not db.query(FormDefinition.id).filter(FormDefinition.id == form_uuid).first():
        raise HTTPException(status_code=404, detail="Form definition not found")
    return (
        db.query(FormVersion)
        .filter(FormVersion.form_id == form_uuid)
        .order_by(FormVersion.created_at.desc())
        .all()
    )


@router.get("/{form_id}/versions/{version_id}", response_model=FormVersionOut)
def get_form_version(form_id: str, version_id: str, db: Session = Depends(get_db)):
    version = (
        db.query(FormVersion)
        .filter(FormVersion.form_id == uuid.UUID(form_id), FormVersion.id == uuid.UUID(version_id))
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Form version not found")
    return version


@router.post("/{form_id}/submissions", response_model=FormSubmissionOut)
def create_form_submission(
    form_id: str,
    payload: FormSubmissionCreate,
    db: Session = Depends(get_db),
):
    form_uuid = uuid.UUID(form_id)
    version = (
        db.query(FormVersion)
        .filter(
            FormVersion.id == payload.version_id,
            FormVersion.form_id == form_uuid,
            FormVersion.status == "published",
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Published form version not found")

    submission = FormSubmission(
        form_id=form_uuid,
        version_id=payload.version_id,
        submission_data=payload.submission_data,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/{form_id}/submissions", response_model=list[FormSubmissionOut])
def list_form_submissions(form_id: str, db: Session = Depends(get_db)):
    form_uuid = uuid.UUID(form_id)
    return (
        db.query(FormSubmission)
        .filter(FormSubmission.form_id == form_uuid)
        .order_by(FormSubmission.submitted_at.desc())
        .all()
    )


@router.get("/{form_id}/submissions/{submission_id}", response_model=FormSubmissionOut)
def get_form_submission(form_id: str, submission_id: str, db: Session = Depends(get_db)):
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.form_id == uuid.UUID(form_id),
            FormSubmission.id == uuid.UUID(submission_id),
        )
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Form submission not found")
    return submission


@router.post("/{form_id}/versions/from-definition")
def save_form_definition_version(
    form_id: str,
    payload: FormDefinitionVersionCreate,
    db: Session = Depends(get_db),
):
    """Save a previously returned complete form JSON as a draft version."""
    layout_tree = payload.form_definition.get("layout_tree")
    if not isinstance(layout_tree, list) or not layout_tree:
        raise HTTPException(status_code=422, detail="form_definition.layout_tree must be a non-empty array")
    form_uuid = uuid.UUID(form_id)
    version_number = payload.version_number or _next_version_number(db, form_uuid, payload.version_bump)
    existing = (
        db.query(FormVersion)
        .filter(FormVersion.form_id == form_uuid, FormVersion.version_number == version_number)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Version {version_number} already exists for this form",
        )
    version = FormVersion(
        form_id=form_uuid,
        version_number=version_number,
        status="draft",
        layout_tree=_snapshot_layout_tree(layout_tree, db),
    )
    db.add(version)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Saving form definition version conflict form_id=%s", form_id)
        raise HTTPException(status_code=409, detail="This form version already exists") from exc
    db.refresh(version)
    logger.info("Saved form definition as version_id=%s", version.id)
    return {"status": "draft_saved", "version_id": str(version.id), "version": version.version_number}


@router.post("/{form_id}/versions")
def create_form_version(form_id: str, payload: FormVersionCreate, db: Session = Depends(get_db)):
    logger.info("POST /api/forms/%s/versions started bump=%s", form_id, payload.version_bump)
    form_uuid = uuid.UUID(form_id)
    version_number = payload.version_number or _next_version_number(db, form_uuid, payload.version_bump)
    existing = (
        db.query(FormVersion)
        .filter(FormVersion.form_id == form_uuid, FormVersion.version_number == version_number)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Version {version_number} already exists for this form",
        )
    version = FormVersion(
        form_id=form_uuid,
        version_number=version_number,
        status="draft",
        layout_tree=_snapshot_layout_tree([node.model_dump() for node in payload.layout_tree], db),
    )
    db.add(version)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.exception("POST /api/forms/%s/versions conflict", form_id)
        raise HTTPException(status_code=409, detail="This form version already exists") from exc
    db.refresh(version)
    logger.info("POST /api/forms/%s/versions completed version_id=%s", form_id, version.id)
    return {"status": "draft_saved", "version_id": str(version.id), "version": version.version_number}


@router.put("/{form_id}/versions/{version_number}/draft")
def update_form_draft(
    form_id: str,
    version_number: str,
    payload: FormDefinitionVersionUpdate,
    db: Session = Depends(get_db),
):
    """Replace an existing draft version until it is published."""
    layout_tree = payload.form_definition.get("layout_tree")
    if not isinstance(layout_tree, list) or not layout_tree:
        raise HTTPException(status_code=422, detail="form_definition.layout_tree must be a non-empty array")

    form_uuid = uuid.UUID(form_id)
    version = (
        db.query(FormVersion)
        .filter(FormVersion.form_id == form_uuid, FormVersion.version_number == version_number)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Draft form version not found")
    if version.status != "draft":
        raise HTTPException(status_code=409, detail="Published form versions cannot be edited")

    version.layout_tree = _snapshot_layout_tree(layout_tree, db)
    db.commit()
    db.refresh(version)
    logger.info("Updated draft form_id=%s version=%s version_id=%s", form_id, version_number, version.id)
    return {"status": "draft_updated", "version_id": str(version.id), "version": version.version_number}


@router.post("/{form_id}/versions/{version_id}/publish")
def publish_form_version(form_id: str, version_id: str, db: Session = Depends(get_db)):
    logger.info("POST /api/forms/%s/versions/%s/publish started", form_id, version_id)
    version = db.query(FormVersion).filter(FormVersion.id == uuid.UUID(version_id)).first()
    if not version:
        raise HTTPException(status_code=404, detail="Form version not found")
    version.status = "published"
    db.commit()
    definition = db.query(FormDefinition).filter(FormDefinition.id == version.form_id).first()
    if definition:
        upsert_published_form(version, definition)
    logger.info("POST /api/forms/%s/versions/%s/publish completed", form_id, version_id)
    return {"status": "published", "version_id": version_id}


@router.delete("/{form_id}/versions/{version_id}")
def delete_form_version(form_id: str, version_id: str, db: Session = Depends(get_db)):
    version = (
        db.query(FormVersion)
        .filter(FormVersion.form_id == uuid.UUID(form_id), FormVersion.id == uuid.UUID(version_id))
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Form version not found")
    if db.query(FormSubmission.id).filter(FormSubmission.version_id == version.id).first():
        raise HTTPException(status_code=409, detail="This version cannot be deleted because it has submissions")

    db.delete(version)
    db.commit()
    delete_published_form(version_id)
    logger.info("DELETE /api/forms/%s/versions/%s completed", form_id, version_id)
    return {"status": "deleted", "version_id": version_id}
