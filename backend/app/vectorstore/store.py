"""Local vector DB (Chroma) built from the Angular Material spec file.

Used by the Field Builder Agent to ground its output in the exact set of
supported components/validations, instead of relying on the LLM's own
(possibly stale or incorrect) knowledge of Angular Material.
"""

import json
import logging
import time
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import get_settings

_embeddings: HuggingFaceEmbeddings | None = None
_vectorstore: Chroma | None = None
logger = logging.getLogger(__name__)


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        settings = get_settings()
        _embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return _embeddings


def _spec_to_documents(spec_path: str) -> list[Document]:
    data = json.loads(Path(spec_path).read_text())
    docs = []
    for field in data.get("supported_fields", []):
        content = (
            f"field type: {field.get('type')}\n"
            f"angular tag: {field.get('angular_tag')}\n"
            f"inner element: {field.get('inner_element', '')}\n"
            f"module: {field.get('module', '')}\n"
            f"requires_options: {field.get('requires_options', False)}\n"
            f"requires_api_config: {field.get('requires_api_config', False)}\n"
            f"allowed_inputs: {', '.join(field.get('allowed_inputs', []))}\n"
            f"allowed_outputs: {', '.join(field.get('allowed_outputs', []))}\n"
            f"allowed_validations: {', '.join(field.get('allowed_validations', []))}\n"
            f"documentation_url: {field.get('documentation_url', '')}"
        )
        docs.append(Document(page_content=content, metadata={"field_type": field.get("type")}))
    return docs


def _get_store(settings) -> Chroma:
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name="angular_material_spec",
        embedding_function=get_embeddings(),
        persist_directory=str(persist_dir),
    )


def build_or_refresh_index() -> int:
    """Rebuild the local vector DB from material_spec.json. Returns doc count."""
    global _vectorstore
    started_at = time.perf_counter()
    settings = get_settings()
    logger.info("Vector refresh started source=%s persist_dir=%s", settings.material_spec_path, settings.chroma_persist_dir)
    docs = _spec_to_documents(settings.material_spec_path)
    logger.info("Vector refresh loaded documents=%d", len(docs))

    store = _get_store(settings)
    existing_ids = store.get()["ids"]
    logger.info("Vector refresh removing existing_documents=%d", len(existing_ids))
    if existing_ids:
        store.delete(ids=existing_ids)
    store.add_documents(docs)

    _vectorstore = store
    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info("Vector refresh completed documents_indexed=%d duration_ms=%.0f", len(docs), duration_ms)
    return len(docs)


def get_retriever(k: int = 4):
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _get_store(get_settings())
    return _vectorstore.as_retriever(search_kwargs={"k": k})
