"""TPS IR Assist agent.

This agent is intentionally separate from Field Builder and Form Builder so it
can grow into the implementation-request workflow coordinator.
"""

import json
import logging
import re
import time
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.tps_ir_assist_tools import load_latest_submitted_form
from app.llm.provider import get_chat_model
from app.vectorstore.store import get_published_form_documents, get_published_form_retriever

logger = logging.getLogger(__name__)


class TpsIrAssistState(TypedDict):
    prompt: str
    messages: list[BaseMessage]
    ir_context: dict[str, Any]
    db: Session
    intent: dict[str, Any]
    show_form_tools: bool
    show_all_forms: bool
    published_forms: list[dict[str, Any]]
    latest_submitted_form: dict[str, Any] | None
    assistant_message: str
    pending_form: dict[str, Any] | None


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

Form assignment is implemented as an explicit confirmation workflow. When the
user asks to use, choose, or assign a form, only discuss candidates supplied in
the published-form context. If multiple published versions match the requested
form and no version was specified, ask the user which version they want; do not
pick one. If one exact form/version is selected, state its exact title and
version and let the UI request confirmation. Never claim that you cannot assign
a form; the UI performs the assignment only after the user confirms.

When the user asks to compare the IR with its latest submitted form, use the
supplied IR record and the complete latest submitted form snapshot and answers.
Compare their meaning, not just identical JSON keys: form labels and IR column
names may differ. Explain the important agreements and differences naturally in
plain text, naming the submitted form and version. Do not output JSON, status
codes, a generated comparison table, or a checklist of every field. Do not
invent values; if a value is blank or cannot be confidently mapped, say so in
plain language. Only compare a submission whose status is submitted; drafts and
released-but-unsubmitted forms are not comparison evidence.
"""


TPS_IR_INTENT_SYSTEM_PROMPT = """You decide whether a TPS IR Assist user message needs published-form tools.
Return STRICT JSON only with these keys:
- show_form_tools: boolean
- show_all_forms: boolean
- form_query: string or null
- wants_assignment: boolean
- compare_latest_submission: boolean
- selected_form_title: string or null
- selected_version_number: string or null

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

Set wants_assignment to true when the user asks to use, select, choose, attach,
or assign a form, including when they answer a form/version clarification from
your recent conversation. For a clarification reply, use the recent history to
identify the selected form and/or version.

Set compare_latest_submission to true when the user asks to compare the IR with
the latest client submission, find differences or mismatches, or check whether
submitted answers agree with IR data. Do not set it for general IR questions.

Set selected_form_title and selected_version_number only when the user's choice
is clear from the current message and recent history. Copy the exact title and
version from that history; never invent IDs, titles, or versions. If the form is
clear but multiple versions remain ambiguous, return its title and a null
version so the assistant can ask which version. If unclear, return null.

If show_form_tools is true, form_query should be the user's form-search intent in
plain language. If show_form_tools is false, form_query must be null. Always
return all seven keys.
"""


_FIELD_QUERY_STOPWORDS = {
    "a", "an", "and", "are", "any", "available", "can", "check", "collect", "could", "details", "do", "does", "find", "for",
    "form", "forms", "from", "have", "if", "is", "list", "me", "my", "not", "number", "of", "published", "request", "show", "suitable", "the", "this", "to",
    "u", "view", "what", "with", "you",
}


def _words(value: str) -> set[str]:
    expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return {word.lower() for word in re.findall(r"[a-zA-Z0-9]+", expanded) if len(word) > 2}


def _matches_requested_field(
    prompt: str,
    field_details: list[dict[str, Any]],
    document_text: str = "",
    title: str = "",
) -> bool:
    requested_words = _words(prompt) - _FIELD_QUERY_STOPWORDS
    if not requested_words:
        return True
    if field_details:
        field_words = set().union(*(_words(f"{field.get('name', '')} {field.get('label', '')}") for field in field_details))
    else:
        field_words = _words(document_text)
    field_words.update(_words(title))
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
    logger.info("IR Assist tool intent classifier started history_messages=%d", len(messages))
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
        parsed = {}

    show_form_tools = bool(parsed.get("show_form_tools"))
    wants_assignment = bool(parsed.get("wants_assignment"))
    compare_latest_submission = bool(parsed.get("compare_latest_submission"))
    if wants_assignment:
        show_form_tools = True
    show_all_forms = bool(parsed.get("show_all_forms")) if show_form_tools else False
    form_query = parsed.get("form_query") if show_form_tools else None
    selected_form_title = parsed.get("selected_form_title")
    selected_version_number = parsed.get("selected_version_number")
    if _is_version_clarification_reply(prompt, messages):
        show_form_tools = True
        show_all_forms = False
        wants_assignment = True
        form_query = prompt
    logger.info(
        "IR Assist intent classified show_form_tools=%s show_all_forms=%s wants_assignment=%s compare_latest_submission=%s",
        show_form_tools,
        show_all_forms,
        wants_assignment,
        compare_latest_submission,
    )
    return {
        "show_form_tools": show_form_tools,
        "show_all_forms": show_all_forms,
        "form_query": form_query if isinstance(form_query, str) and form_query.strip() else None,
        "wants_assignment": wants_assignment,
        "compare_latest_submission": compare_latest_submission,
        "selected_form_title": selected_form_title if isinstance(selected_form_title, str) else None,
        "selected_version_number": selected_version_number if isinstance(selected_version_number, str) else None,
    }


def _is_version_clarification_reply(prompt: str, messages: list[BaseMessage]) -> bool:
    latest_assistant_message = next(
        (str(message.content) for message in reversed(messages) if message.type == "ai"),
        "",
    )
    asked_for_version = re.search(
        r"which version|what version|multiple published versions",
        latest_assistant_message,
        re.IGNORECASE,
    )
    contains_version = re.search(r"(?<!\d)(?:version\s*)?v?\d+\.\d+\.\d+(?!\d)", prompt, re.IGNORECASE)
    return bool(asked_for_version and contains_version)


def _resolve_pending_form(
    prompt: str,
    messages: list[BaseMessage],
    published_forms: list[dict[str, Any]],
    intent: dict[str, Any],
    show_all_forms: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve an assignment only to an indexed candidate with an exact version."""
    if not intent.get("wants_assignment") or show_all_forms or not published_forms:
        logger.info(
            "IR Assist tool resolve_pending_form skipped wants_assignment=%s show_all_forms=%s candidate_count=%d",
            intent.get("wants_assignment"),
            show_all_forms,
            len(published_forms),
        )
        return None, None

    recent_user_text = " ".join(
        str(message.content)
        for message in messages[-8:]
        if message.type == "human"
    )
    selection_text = f"{recent_user_text} {prompt}".casefold()
    selected_title = str(intent.get("selected_form_title") or "").strip()
    title_matches = [
        form for form in published_forms
        if selected_title and str(form.get("title", "")).casefold() == selected_title.casefold()
    ]
    if not title_matches:
        title_matches = [
            form for form in published_forms
            if str(form.get("title", "")).casefold() in selection_text
        ]
    if not title_matches and len(published_forms) == 1:
        title_matches = published_forms
    if not title_matches:
        titles = sorted({str(form.get("title", "")) for form in published_forms})
        if len(titles) > 1:
            logger.info("IR Assist tool resolve_pending_form needs form clarification candidate_titles=%d", len(titles))
            return None, f"Which form would you like to assign? Available published forms: {', '.join(titles)}."
        return None, None

    selected_version = str(intent.get("selected_version_number") or "").strip()
    if not selected_version:
        version_match = re.search(
            r"(?<!\d)(?:version\s*)?v?(\d+\.\d+\.\d+)(?!\d)",
            prompt,
            re.IGNORECASE,
        )
        selected_version = version_match.group(1) if version_match else ""

    if selected_version:
        version_matches = [
            form for form in title_matches
            if str(form.get("version_number", "")).casefold() == selected_version.casefold()
        ]
        if len(version_matches) == 1:
            logger.info(
                "IR Assist tool resolve_pending_form selected form_id=%s version_id=%s version=%s",
                version_matches[0].get("form_id"),
                version_matches[0].get("version_id"),
                version_matches[0].get("version_number"),
            )
            return version_matches[0], None
        versions = ", ".join(sorted({str(form.get("version_number", "")) for form in title_matches}))
        logger.info("IR Assist tool resolve_pending_form requested version unavailable available_versions=%d", len(title_matches))
        return None, f"I couldn't find published version {selected_version} of {title_matches[0]['title']}. Available versions: {versions}."

    if len(title_matches) == 1:
        logger.info(
            "IR Assist tool resolve_pending_form selected form_id=%s version_id=%s version=%s",
            title_matches[0].get("form_id"),
            title_matches[0].get("version_id"),
            title_matches[0].get("version_number"),
        )
        return title_matches[0], None

    versions = ", ".join(sorted({str(form.get("version_number", "")) for form in title_matches}))
    logger.info("IR Assist tool resolve_pending_form needs version clarification version_count=%d", len(title_matches))
    return None, f"I found multiple published versions of {title_matches[0]['title']}: {versions}. Which version would you like me to use?"


def _classify_intent_node(state: TpsIrAssistState) -> dict[str, Any]:
    intent = _classify_form_tool_intent(state["prompt"], state["messages"], state["ir_context"])
    return {
        "intent": intent,
        "show_form_tools": bool(intent.get("show_form_tools")),
        "show_all_forms": bool(intent.get("show_all_forms")),
    }


def _route_after_intent(state: TpsIrAssistState) -> str:
    if state["show_form_tools"]:
        return "retrieve_published_forms"
    if state["intent"].get("compare_latest_submission"):
        return "load_latest_submitted_form"
    return "answer"


def _retrieve_published_forms_node(state: TpsIrAssistState) -> dict[str, Any]:
    ir_number = state["ir_context"].get("ir_number")
    intent = state["intent"]
    form_query = intent.get("form_query") or state["prompt"]
    logger.info(
        "IR Assist published-form retrieval started ir_number=%s show_all=%s wants_assignment=%s",
        ir_number,
        state["show_all_forms"],
        intent.get("wants_assignment"),
    )
    try:
        if state["show_all_forms"]:
            documents = get_published_form_documents()
        else:
            all_documents = get_published_form_documents()
            selected_title = str(intent.get("selected_form_title") or "").strip()
            if selected_title:
                documents = [
                    document for document in all_documents
                    if str(document.metadata.get("title", "")).casefold() == selected_title.casefold()
                ]
            else:
                logger.info("IR Assist tool published_form_vector_search started")
                relevant_documents = get_published_form_retriever(k=5).invoke(form_query)
                relevant_titles = {
                    str(document.metadata.get("title", "")).casefold()
                    for document in relevant_documents
                    if document.metadata.get("title")
                }
                # Include all indexed versions of semantically retrieved forms.
                documents = [
                    document for document in all_documents
                    if str(document.metadata.get("title", "")).casefold() in relevant_titles
                ]
                logger.info(
                    "IR Assist tool published_form_vector_search completed retrieved_documents=%d matched_titles=%d",
                    len(relevant_documents),
                    len(relevant_titles),
                )
    except Exception:
        logger.exception("IR Assist published-form retrieval failed ir_number=%s", ir_number)
        raise

    forms = []
    for document in documents:
        try:
            field_details = json.loads(document.metadata.get("field_details", "[]"))
        except json.JSONDecodeError:
            field_details = []
        title = str(document.metadata.get("title", ""))
        if state["show_all_forms"] or intent.get("wants_assignment") or _matches_requested_field(
            form_query,
            field_details,
            document.page_content,
            title,
        ):
            forms.append({
                "form_id": document.metadata.get("form_id"),
                "version_id": document.metadata.get("version_id"),
                "title": title or "Published form",
                "version_number": document.metadata.get("version_number", ""),
                "fields": field_details,
            })
    logger.info("IR Assist published-form retrieval completed candidate_count=%d", len(forms))
    return {"published_forms": forms}


def _route_after_published_forms(state: TpsIrAssistState) -> str:
    return "load_latest_submitted_form" if state["intent"].get("compare_latest_submission") else "answer"


def _load_latest_submitted_form_node(state: TpsIrAssistState) -> dict[str, Any]:
    submission = load_latest_submitted_form(state["db"], state["ir_context"].get("id"))
    return {"latest_submitted_form": submission}


def _answer_node(state: TpsIrAssistState) -> dict[str, Any]:
    intent = state["intent"]
    published_forms = state["published_forms"]
    compare_requested = bool(intent.get("compare_latest_submission"))
    submitted_form = state["latest_submitted_form"]
    form_context = (
        "PUBLISHED FORM CANDIDATES (authoritative IDs and versions; choose only from these):\n"
        f"{json.dumps(published_forms, ensure_ascii=False) or 'No published form candidates were retrieved.'}"
        if state["show_form_tools"]
        else "Form tools were not requested for this turn. Do not discuss form availability unless the user asks about forms."
    )
    submitted_context = (
        "LATEST SUBMITTED FORM (authoritative snapshot and client answers; compare by meaning, not exact key names):\n"
        f"{json.dumps(submitted_form, ensure_ascii=False, default=str)}"
        if compare_requested and submitted_form
        else (
            "No form with status submitted exists for this IR. Draft or released-but-unsubmitted forms are not eligible for comparison."
            if compare_requested
            else "Submitted-form data is not included for this turn."
        )
    )
    logger.info(
        "IR Assist answer node started ir_number=%s compare_requested=%s submitted_context_available=%s published_candidate_count=%d",
        state["ir_context"].get("ir_number"),
        compare_requested,
        bool(submitted_form),
        len(published_forms),
    )
    model = get_chat_model(temperature=0.2)
    try:
        response = model.invoke([
            SystemMessage(content=(
                f"{TPS_IR_ASSIST_SYSTEM_PROMPT}\n"
                f"CURRENT IR CONTEXT:\n{json.dumps(state['ir_context'], default=str)}\n\n"
                f"{form_context}\n\n{submitted_context}"
            )),
            *state["messages"],
            HumanMessage(content=state["prompt"]),
        ])
    except Exception:
        logger.exception("IR Assist answer node LLM call failed ir_number=%s", state["ir_context"].get("ir_number"))
        raise

    answer = str(response.content).strip()
    pending_form, selection_message = _resolve_pending_form(
        state["prompt"],
        state["messages"],
        published_forms,
        intent,
        state["show_all_forms"],
    )
    if selection_message:
        answer = selection_message
    elif pending_form:
        answer = f"I found **{pending_form['title']}** version {pending_form['version_number']}. Please confirm to assign this exact version to the IR."
    updated_messages = [*state["messages"], HumanMessage(content=state["prompt"]), AIMessage(content=answer)]
    logger.info(
        "IR Assist answer node completed ir_number=%s response_chars=%d pending_form=%s",
        state["ir_context"].get("ir_number"),
        len(answer),
        bool(pending_form),
    )
    return {"assistant_message": answer, "messages": updated_messages, "pending_form": pending_form}


def build_graph():
    graph = StateGraph(TpsIrAssistState)
    graph.add_node("classify_intent", _classify_intent_node)
    graph.add_node("retrieve_published_forms", _retrieve_published_forms_node)
    graph.add_node("load_latest_submitted_form", _load_latest_submitted_form_node)
    graph.add_node("answer", _answer_node)
    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        _route_after_intent,
        {
            "retrieve_published_forms": "retrieve_published_forms",
            "load_latest_submitted_form": "load_latest_submitted_form",
            "answer": "answer",
        },
    )
    graph.add_conditional_edges(
        "retrieve_published_forms",
        _route_after_published_forms,
        {"load_latest_submitted_form": "load_latest_submitted_form", "answer": "answer"},
    )
    graph.add_edge("load_latest_submitted_form", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


_GRAPH = None


def get_tps_ir_assist_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_tps_ir_assist(
    prompt: str,
    messages: list[BaseMessage],
    ir_context: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    """Run the IR Assist classify -> tools -> answer graph for one turn."""
    started_at = time.perf_counter()
    logger.info("TPS IR Assist graph run started ir_number=%s", ir_context.get("ir_number"))
    result = get_tps_ir_assist_graph().invoke({
        "prompt": prompt,
        "messages": messages,
        "ir_context": ir_context,
        "db": db,
        "intent": {},
        "show_form_tools": False,
        "show_all_forms": False,
        "published_forms": [],
        "latest_submitted_form": None,
        "assistant_message": "",
        "pending_form": None,
    })
    logger.info(
        "TPS IR Assist graph run completed ir_number=%s duration_ms=%.0f",
        ir_context.get("ir_number"),
        (time.perf_counter() - started_at) * 1000,
    )
    return result
