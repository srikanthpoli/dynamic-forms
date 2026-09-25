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


TPS_IR_INTENT_SYSTEM_PROMPT = """You decide whether a TPS IR Assist user message needs published-form tools.
Return STRICT JSON only with these keys:
- show_form_tools: boolean
- show_all_forms: boolean
- form_query: string or null

The CURRENT user message is authoritative. Set show_form_tools to true only when
the current user message explicitly asks to find, list, show, check availability
of, inspect, assign, release, or submit forms/fields/templates.
Set it to false for general IR questions about the customer, IR number, status,
priority, address, risk, onboarding type, notes, or summaries.
Set it to false for generic follow-ups like "tell me more", "explain more",
"what else", "give details", or "summarize" unless that current message
explicitly mentions forms, fields, templates, submissions, or uses a pronoun
that clearly refers to forms from the immediately previous user message.

Set show_all_forms to true only when the user explicitly asks to list/show/view
all available or published forms. Otherwise false.

If show_form_tools is true, form_query should be the user's form-search intent in
plain language. If show_form_tools is false, form_query must be null.
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


def _parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


def _classify_form_tool_intent(prompt: str, messages: list[BaseMessage], ir_context: dict[str, Any]) -> dict[str, Any]:
    model = get_chat_model(temperature=0, json_mode=True)
    history = [
        {"type": message.type, "content": str(message.content)}
        for message in messages[-6:]
    ]
    response = model.invoke([
        SystemMessage(content=TPS_IR_INTENT_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps({
            "user_message": prompt,
            "recent_history": history,
            "ir_context": ir_context,
        }, default=str)),
    ])
    try:
        parsed = _parse_json_response(str(response.content))
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("TPS IR Assist intent parse failed; hiding form tools by default: %s", exc)
        return {"show_form_tools": False, "show_all_forms": False, "form_query": None}

    show_form_tools = bool(parsed.get("show_form_tools"))
    show_all_forms = bool(parsed.get("show_all_forms")) if show_form_tools else False
    form_query = parsed.get("form_query") if show_form_tools else None
    logger.info(
        "TPS IR Assist intent classified show_form_tools=%s show_all_forms=%s form_query=%s prompt=%s",
        show_form_tools,
        show_all_forms,
        form_query,
        prompt,
    )
    return {
        "show_form_tools": show_form_tools,
        "show_all_forms": show_all_forms,
        "form_query": form_query if isinstance(form_query, str) and form_query.strip() else None,
    }


def choose_pending_form(prompt: str, published_forms: list[dict[str, Any]], show_all_forms: bool) -> dict[str, Any] | None:
    """Choose the candidate the user named, instead of trusting retriever order."""
    if show_all_forms or not published_forms:
        return None

    normalized_prompt = prompt.casefold()
    exact_matches = [
        form for form in published_forms
        if str(form.get("title", "")).casefold() in normalized_prompt
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    version_matches = [
        form for form in exact_matches or published_forms
        if str(form.get("version_number", "")).casefold() in normalized_prompt
    ]
    if len(version_matches) == 1:
        return version_matches[0]

    return published_forms[0] if len(published_forms) == 1 else None


def run_tps_ir_assist(
    prompt: str,
    messages: list[BaseMessage],
    ir_context: dict[str, Any],
) -> dict[str, Any]:
    """Answer using the stored IR context and conversation history."""
    logger.info("TPS IR Assist run started ir_number=%s", ir_context.get("ir_number"))
    intent = _classify_form_tool_intent(prompt, messages, ir_context)
    show_form_tools = bool(intent["show_form_tools"])
    show_all_forms = bool(intent["show_all_forms"])
    form_query = intent.get("form_query") or prompt
    retrieved_candidates = []
    if show_form_tools:
        retrieved_candidates = (
            get_published_form_documents()
            if show_all_forms
            else get_published_form_retriever(k=5).invoke(form_query)
        )
    form_candidates = []
    for document in retrieved_candidates:
        try:
            field_details = json.loads(document.metadata.get("field_details", "[]"))
        except json.JSONDecodeError:
            field_details = []
        if show_all_forms or _matches_requested_field(form_query, field_details, document.page_content):
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
    form_context_message = (
        f"PUBLISHED FORM CANDIDATES:\n{published_forms_context or 'No published form candidates were retrieved.'}"
        if show_form_tools
        else "PUBLISHED FORM CANDIDATES: Form tools were not requested for this turn. Do not discuss form availability unless the user asks about forms."
    )
    response = model.invoke([
        SystemMessage(content=(
            f"{TPS_IR_ASSIST_SYSTEM_PROMPT}\n"
            f"CURRENT IR CONTEXT:\n{json.dumps(ir_context, default=str)}\n\n"
            f"{form_context_message}"
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
        "show_form_tools": show_form_tools,
        "pending_form": choose_pending_form(prompt, published_forms, show_all_forms),
    }
