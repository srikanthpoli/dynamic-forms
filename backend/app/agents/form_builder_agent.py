"""Form Builder Agent.

A LangGraph flow that assembles a form layout from already-published field
templates in Postgres, based on a free-text user prompt (e.g. "build me a
customer onboarding form"). It only selects from published templates - it
does not invent new fields (that is the Field Builder Agent's job).
"""

import json
import logging
import time
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.db.models import FieldTemplate
from app.llm.provider import get_chat_model

logger = logging.getLogger(__name__)

MISSING_FIELD_MESSAGE = (
    "Some fields requested for this form are not available in the field library yet. "
    "Please build the needed fields using Field Builder first, then return here to add them to the form."
)


class FormBuilderState(TypedDict):
    prompt: str
    messages: list[BaseMessage]
    available_templates: list[dict]
    layout_tree: list[dict]
    form_definition: dict
    assistant_message: str


def _parse_json(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


def _make_fetch_templates(db: Session):
    def _fetch_templates(state: FormBuilderState) -> FormBuilderState:
        templates = db.query(FieldTemplate).all()
        state["available_templates"] = [
            {
                "field_id": str(t.id),
                "name": t.name,
                "label": t.label,
                "field_type": t.field_type,
                "angular_config": t.angular_config,
                "validation_rules": t.validation_rules,
                "api_config": t.api_config,
            }
            for t in templates
        ]
        logger.info("Form agent loaded templates=%d", len(state["available_templates"]))
        return state

    return _fetch_templates


def _arrange_layout(state: FormBuilderState) -> FormBuilderState:
    llm = get_chat_model(temperature=0.2, json_mode=True)

    system = SystemMessage(content=(
        "You are a history-aware form layout assistant. Choose which of the AVAILABLE field "
        "templates best satisfy the user's request and order them logically. "
        "Only select field_id values from the provided list; never invent new "
        "fields or field_ids.\n"
        f"AVAILABLE TEMPLATES: {json.dumps(state['available_templates'])}\n\n"
        "Use the conversation history to refine the previous form. Preserve "
        "existing fields unless the user asks to add, remove, or replace them.\n"
        f"CURRENT FORM: {json.dumps(state['form_definition'])}\n"
        f"CURRENT LAYOUT: {json.dumps(state['layout_tree'])}\n\n"
        "If the request needs a field or capability that is not represented by an AVAILABLE "
        "TEMPLATE, do not invent it and do not alter the current layout. Set missing_fields to "
        "true and use a generic assistant_message without naming any specific field.\n"
        'Return STRICT JSON only: {"title": "...", "description": "...", '
        '"layout": [{"field_id": "...", "order": 0, "column_span": 12}, ...], '
        '"missing_fields": false, "assistant_message": "..."}'
    ))

    response = llm.invoke([
        system,
        *state["messages"],
        HumanMessage(content=state["prompt"]),
    ])
    parsed = _parse_json(response.content)
    if isinstance(parsed, dict):
        missing_fields = parsed.get("missing_fields")
        state["assistant_message"] = parsed.get("assistant_message") or ""
        layout = parsed.get("layout")
        if missing_fields is True or (isinstance(missing_fields, list) and missing_fields) or not isinstance(layout, list):
            state["assistant_message"] = MISSING_FIELD_MESSAGE
        else:
            state["layout_tree"] = layout
            state["form_definition"] = {
                "title": parsed.get("title") or state["form_definition"].get("title", "Untitled Form"),
                "description": parsed.get("description") or state["form_definition"].get("description"),
                "layout_tree": state["layout_tree"],
            }
    state["messages"] = [
        *state["messages"],
        HumanMessage(content=state["prompt"]),
        AIMessage(content=response.content),
    ]
    return state


def build_graph(db: Session):
    graph = StateGraph(FormBuilderState)
    graph.add_node("fetch_templates", _make_fetch_templates(db))
    graph.add_node("arrange_layout", _arrange_layout)
    graph.add_edge(START, "fetch_templates")
    graph.add_edge("fetch_templates", "arrange_layout")
    graph.add_edge("arrange_layout", END)
    return graph.compile()


def run_form_builder(
    prompt: str,
    db: Session,
    messages: list[BaseMessage],
    previous_layout: list[dict],
    form_definition: dict,
) -> FormBuilderState:
    started_at = time.perf_counter()
    logger.info("Form agent run started")
    graph = build_graph(db)
    result = graph.invoke({
        "prompt": prompt,
        "messages": messages,
        "available_templates": [],
        "layout_tree": previous_layout,
        "form_definition": form_definition,
        "assistant_message": "",
    })
    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info("Form agent run completed layout_nodes=%d duration_ms=%.0f", len(result["layout_tree"]), duration_ms)
    return result
