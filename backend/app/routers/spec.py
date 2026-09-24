import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.capabilities.generator import OFFICIAL_DOCS, generate_capabilities
from app.vectorstore.store import build_or_refresh_index

router = APIRouter(prefix="/api/spec", tags=["spec"])
logger = logging.getLogger(__name__)


class CapabilityGenerationRequest(BaseModel):
    components: list[str] = Field(
        default_factory=lambda: list(OFFICIAL_DOCS),
        description="Supported field types to regenerate from official Angular Material documentation.",
    )


@router.post("/refresh")
def refresh_spec_index():
    """Re-read material_spec.json, re-embed it, and rebuild the local vector DB.

    No request body is required. Click Try it out, then Execute.
    """
    logger.info("POST /api/spec/refresh started")
    try:
        count = build_or_refresh_index()
    except Exception:
        logger.exception("POST /api/spec/refresh failed")
        raise
    logger.info("POST /api/spec/refresh completed documents_indexed=%d", count)
    return {"status": "success", "documents_indexed": count}


@router.post("/generate-capabilities")
def generate_capability_registry(payload: CapabilityGenerationRequest):
    """Fetch official Angular Material docs, regenerate the scoped registry, and refresh Chroma."""
    logger.info("POST /api/spec/generate-capabilities started components=%s", payload.components)
    try:
        registry = generate_capabilities(payload.components)
    except ValueError as exc:
        logger.exception("POST /api/spec/generate-capabilities validation failed")
        raise HTTPException(status_code=502, detail=f"Capability generation returned invalid data: {exc}") from exc
    except Exception as exc:
        logger.exception("POST /api/spec/generate-capabilities failed")
        raise HTTPException(status_code=502, detail="Unable to generate capabilities from Angular Material documentation") from exc
    return {
        "status": "success",
        "components": payload.components,
        "registry": registry,
    }
