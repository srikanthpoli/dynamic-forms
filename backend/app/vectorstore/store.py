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
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import FieldTemplate, FormDefinition, FormVersion

_embeddings: HuggingFaceEmbeddings | None = None
_vectorstore: Chroma | None = None
_field_store: Chroma | None = None
_form_store: Chroma | None = None
logger = logging.getLogger(__name__)

SPEC_COLLECTION = "angular_material_spec"
FIELD_COLLECTION = "published_fields"
FORM_COLLECTION = "published_forms"


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


def _get_store(settings, collection_name: str) -> Chroma:
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
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

    store = _get_store(settings, SPEC_COLLECTION)
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
        _vectorstore = _get_store(get_settings(), SPEC_COLLECTION)
    return _vectorstore.as_retriever(search_kwargs={"k": k})


def _field_document(field: FieldTemplate) -> Document:
    content = (
        f"published field name: {field.name}\n"
        f"label: {field.label}\n"
        f"field type: {field.field_type}\n"
        f"validation rules: {json.dumps(field.validation_rules)}\n"
        f"validation messages: {json.dumps(field.validation_messages)}\n"
        f"angular configuration: {json.dumps(field.angular_config)}\n"
        f"api configuration: {json.dumps(field.api_config)}"
    )
    return Document(
        page_content=content,
        metadata={"field_id": str(field.id), "name": field.name, "field_type": field.field_type},
    )


def _form_document(version: FormVersion, definition: FormDefinition) -> Document:
    fields = [node.get("field", {}) for node in version.layout_tree or []]
    labels = [field.get("label") for field in fields if field.get("label")]
    names = [field.get("name") for field in fields if field.get("name")]
    types = [field.get("field_type") for field in fields if field.get("field_type")]
    content = (
        f"published form title: {definition.title}\n"
        f"description: {definition.description or ''}\n"
        f"version: {version.version_number}\n"
        f"field labels: {', '.join(labels)}\n"
        f"field names: {', '.join(names)}\n"
        f"field types: {', '.join(types)}"
    )
    return Document(
        page_content=content,
        metadata={
            "form_id": str(definition.id),
            "version_id": str(version.id),
            "title": definition.title,
            "version_number": version.version_number,
            "field_details": json.dumps([
                {
                    "name": field.get("name"),
                    "label": field.get("label"),
                    "validation_rules": field.get("validation_rules", {}),
                }
                for field in fields
            ]),
        },
    )


def _replace_documents(store: Chroma, documents: list[Document], ids: list[str]) -> int:
    existing_ids = store.get()["ids"]
    if existing_ids:
        store.delete(ids=existing_ids)
    if documents:
        store.add_documents(documents, ids=ids)
    return len(documents)


def _upsert_document(store: Chroma, document: Document, document_id: str) -> None:
    existing_ids = set(store.get()["ids"])
    if document_id in existing_ids:
        store.update_documents(ids=[document_id], documents=[document])
    else:
        store.add_documents(documents=[document], ids=[document_id])


def refresh_published_fields_index(db: Session) -> int:
    global _field_store
    store = _get_store(get_settings(), FIELD_COLLECTION)
    fields = db.query(FieldTemplate).all()
    count = _replace_documents(store, [_field_document(field) for field in fields], [str(field.id) for field in fields])
    _field_store = store
    logger.info("Published field index refreshed documents=%d", count)
    return count


def refresh_published_forms_index(db: Session) -> int:
    global _form_store
    store = _get_store(get_settings(), FORM_COLLECTION)
    rows = (
        db.query(FormVersion, FormDefinition)
        .join(FormDefinition, FormDefinition.id == FormVersion.form_id)
        .filter(FormVersion.status == "published")
        .all()
    )
    count = _replace_documents(
        store,
        [_form_document(version, definition) for version, definition in rows],
        [str(version.id) for version, _ in rows],
    )
    _form_store = store
    logger.info("Published form index refreshed documents=%d", count)
    return count


def upsert_published_field(field: FieldTemplate) -> None:
    global _field_store
    store = _field_store or _get_store(get_settings(), FIELD_COLLECTION)
    _upsert_document(store, _field_document(field), str(field.id))
    _field_store = store


def delete_published_field(field_id: str) -> None:
    global _field_store
    store = _field_store or _get_store(get_settings(), FIELD_COLLECTION)
    if str(field_id) in store.get()["ids"]:
        store.delete(ids=[str(field_id)])
    _field_store = store


def upsert_published_form(version: FormVersion, definition: FormDefinition) -> None:
    global _form_store
    store = _form_store or _get_store(get_settings(), FORM_COLLECTION)
    _upsert_document(store, _form_document(version, definition), str(version.id))
    _form_store = store


def delete_published_form(version_id: str) -> None:
    global _form_store
    store = _form_store or _get_store(get_settings(), FORM_COLLECTION)
    if str(version_id) in store.get()["ids"]:
        store.delete(ids=[str(version_id)])
    _form_store = store


def get_published_field_retriever(k: int = 4):
    global _field_store
    _field_store = _field_store or _get_store(get_settings(), FIELD_COLLECTION)
    return _field_store.as_retriever(search_kwargs={"k": k})


def get_published_form_retriever(k: int = 4):
    global _form_store
    _form_store = _form_store or _get_store(get_settings(), FORM_COLLECTION)
    return _form_store.as_retriever(search_kwargs={"k": k})


def get_published_form_documents() -> list[Document]:
    """Return every indexed published form document for explicit list requests."""
    global _form_store
    _form_store = _form_store or _get_store(get_settings(), FORM_COLLECTION)
    records = _form_store.get(include=["documents", "metadatas"])
    return [
        Document(page_content=content or "", metadata=metadata or {})
        for content, metadata in zip(records.get("documents", []), records.get("metadatas", []))
    ]
