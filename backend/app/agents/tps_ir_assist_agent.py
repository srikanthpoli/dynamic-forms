"""TPS IR Assist agent.

This agent is intentionally separate from Field Builder and Form Builder so it
can grow into the implementation-request workflow coordinator.
"""

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.llm.provider import get_chat_model
from app.vectorstore.store import get_published_form_documents, get_published_form_retriever

logger = logging.getLogger(__name__)


TPS_IR_ASSIST_SYSTEM_PROMPT = """You are TPS IR Assist, an assistant for a single implementation request.
Use only the supplied IR context when answering. Do not invent customer facts,
form assignments, submission data, or workflow state. If the context is not
sufficient, say what information is missing.

When the user asks whether a form is available or present, answer that question
directly in natural language by stating whether it is present or not present.
Do not add form details, recommendations, next steps, or any other information
unless the user explicitly asks for them.

When the user asks to show, list, or see available/published forms, include every
form supplied in the candidates context. Do not limit the answer to one form and
do not ask the user to choose before showing the list.

Published form availability is separate from forms assigned to the current IR.
Use the PUBLISHED FORM CANDIDATES context when answering form availability
questions. If candidates are present, a published form is available globally;
do not claim that no form exists merely because it is not assigned to this IR.
If the candidates context is empty for a targeted request, say that no matching
published form was found and ask: "Would you like me to list all published
forms?" Do not recommend, assign, or present a first form when no match exists.
For an explicit list/show request, list every supplied form and do not ask the
user to choose or present an assignment confirmation.

Answer naturally and conversationally first. For example: "Yes, I found a
published form that can collect those details." or "I could not find a
published form for that request." Do not simply dump the available forms.
When the user asks for the matching form's details, follow the natural-language
answer with this readable Markdown structure:
**Form: <form name>**
Version: <version>
Fields:
- **<field label>** (<field name>) — Validations: <validation summary>
Put each field on its own line. Do not add unrelated forms, JSON, or extra
recommendations unless the user explicitly asks for them.

For now, answer questions conversationally. Future capabilities may include
finding suitable published forms, assigning forms to the IR, and coordinating
client onboarding. Do not perform those actions unless explicitly implemented
and requested by a tool-enabled workflow.
"""


_FIELD_QUERY_STOPWORDS = {
    "a", "an", "and", "are", "any", "available", "can", "check", "collect", "could", "details", "do", "does", "find", "for",
    "form", "forms", "from", "have", "if", "is", "list", "me", "my", "not", "number", "of", "published", "request", "show", "suitable", "the", "this", "to",
    "u", "view", "what", "with", "you",
}


def _words(value: str) -> set[str]:
    expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return {word.lower() for word in re.findall(r"[a-zA-Z0-9]+", expanded) if len(word) > 2}


def _matches_requested_field(prompt: str, field_details: list[dict[str, Any]], document_text: str = "") -> bool:
    requested_words = _words(prompt) - _FIELD_QUERY_STOPWORDS
    if not requested_words:
        return True
    if field_details:
        field_words = set().union(*(_words(f"{field.get('name', '')} {field.get('label', '')}") for field in field_details))
    else:
        field_words = _words(document_text)
    return bool(requested_words & field_words)


def _is_generic_form_request(prompt: str) -> bool:
    words = _words(prompt)
    return bool(words & {"form", "forms"}) and not (words - _FIELD_QUERY_STOPWORDS - {"form", "forms"})


def run_tps_ir_assist(
    prompt: str,
    messages: list[BaseMessage],
    ir_context: dict[str, Any],
) -> dict[str, Any]:
    """Answer using the stored IR context and conversation history."""
    logger.info("TPS IR Assist run started ir_number=%s", ir_context.get("ir_number"))
    show_all_forms = bool(
        re.search(r"\b(show|list|display|view|see)\b.*\bforms?\b", prompt, re.IGNORECASE)
        or re.search(r"\b(available|published)\s+forms?\b", prompt, re.IGNORECASE)
        or _is_generic_form_request(prompt)
    )
    retrieved_candidates = (
        get_published_form_documents()
        if show_all_forms
        else get_published_form_retriever(k=5).invoke(prompt)
    )
    form_candidates = []
    for document in retrieved_candidates:
        try:
            field_details = json.loads(document.metadata.get("field_details", "[]"))
        except json.JSONDecodeError:
            field_details = []
        if show_all_forms or _matches_requested_field(prompt, field_details, document.page_content):
            form_candidates.append(document)
    published_forms_context = "\n---\n".join(document.page_content for document in form_candidates)
    published_forms = []
    for document in form_candidates:
        metadata = document.metadata
        try:
            field_details = json.loads(metadata.get("field_details", "[]"))
        except json.JSONDecodeError:
            field_details = []
        published_forms.append({
            "form_id": metadata.get("form_id"),
            "version_id": metadata.get("version_id"),
            "title": metadata.get("title", "Published form"),
            "version_number": metadata.get("version_number", ""),
            "fields": field_details,
        })
    model = get_chat_model(temperature=0.2)
    response = model.invoke([
        SystemMessage(content=(
            f"{TPS_IR_ASSIST_SYSTEM_PROMPT}\n"
            f"CURRENT IR CONTEXT:\n{json.dumps(ir_context, default=str)}\n\n"
            f"PUBLISHED FORM CANDIDATES:\n{published_forms_context or 'No published form candidates were retrieved.'}"
        )),
        *messages,
        HumanMessage(content=prompt),
    ])
    answer = str(response.content).strip()
    updated_messages = [*messages, HumanMessage(content=prompt), AIMessage(content=answer)]
    logger.info("TPS IR Assist run completed ir_number=%s", ir_context.get("ir_number"))
    return {
        "assistant_message": answer,
        "messages": updated_messages,
        "published_forms": published_forms,
        "show_all_forms": show_all_forms,
    }
