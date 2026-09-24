"""Field Builder Agent.

A LangGraph flow that drafts an Angular Material field template from a user
prompt. It is grounded in the local vector DB (material_spec.json embeddings)
and is history-aware: pass in the session's prior messages and it will refine
the previous draft rather than starting over, until the caller is happy and
publishes it.
"""

import json
import logging
import time
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.llm.provider import get_chat_model
from app.vectorstore.store import get_retriever

logger = logging.getLogger(__name__)


class FieldBuilderState(TypedDict):
    prompt: str
    messages: list[BaseMessage]
    spec_context: str
    draft: dict
    assistant_message: str
    field_context: dict | None


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


def _retrieve_context(state: FieldBuilderState) -> FieldBuilderState:
    logger.info("Field agent retrieval started history_messages=%d", len(state["messages"]))
    retriever = get_retriever()
    docs = retriever.invoke(state["prompt"])
    state["spec_context"] = "\n---\n".join(d.page_content for d in docs)
    logger.info("Field agent retrieval completed documents=%d", len(docs))
    return state


def _generate_field(state: FieldBuilderState) -> FieldBuilderState:
    logger.info("Field agent generation started history_messages=%d", len(state["messages"]))
    llm = get_chat_model(temperature=0.1, json_mode=True)

    system = SystemMessage(content=(
        "You are an AI form schema generator for an Angular Material application. "
        "Ground every answer strictly in these retrieved component mappings from "
        f"the local vector DB:\n{state['spec_context']}\n\n"
        f"CURRENT FIELD CONTEXT: {json.dumps(state['field_context'])}\n\n"
        "Return STRICT JSON only with exactly these top-level keys: "
        "assistant_message and field_template. assistant_message must be a concise, "
        "human-readable explanation of what you created or changed, including the "
        "field label, type, and important validation behavior. field_template must "
        "contain name, field_id, field_type, label, angular_config (object with "
        "angular_tag and inner_element), validation_rules, validation_messages, "
        "and optionally api_config "
        "or options depending on field_type. If the conversation history below already contains a draft "
        "for this field, treat the new prompt as a refinement of it rather than "
        "starting over, unless the user clearly asks for something different."
    ))

    messages: list[BaseMessage] = [system, *state["messages"], HumanMessage(content=state["prompt"])]
    response = llm.invoke(messages)

    generated = _parse_json(response.content)
    draft = generated.get("field_template", generated)
    assistant_message = generated.get("assistant_message")
    if not isinstance(assistant_message, str) or not assistant_message.strip():
        raise ValueError("Field Builder response must include a human-readable assistant_message")
    validation_messages = draft.get("validation_messages")
    if not isinstance(validation_messages, dict) or any(
        not isinstance(value, str) or not value.strip()
        for value in validation_messages.values()
    ):
        raise ValueError("Field Builder response must include human-readable validation_messages")

    state["messages"] = [
        *state["messages"],
        HumanMessage(content=state["prompt"]),
        AIMessage(content=response.content),
    ]
    state["draft"] = draft
    state["assistant_message"] = assistant_message.strip()
    logger.info("Field agent generation completed field_type=%s", draft.get("field_type", "unknown"))
    return state


def build_graph():
    graph = StateGraph(FieldBuilderState)
    graph.add_node("retrieve_context", _retrieve_context)
    graph.add_node("generate_field", _generate_field)
    graph.add_edge(START, "retrieve_context")
    graph.add_edge("retrieve_context", "generate_field")
    graph.add_edge("generate_field", END)
    return graph.compile()


_GRAPH = None


def get_field_builder_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_field_builder(prompt: str, messages: list[BaseMessage], field_context: dict | None = None) -> FieldBuilderState:
    started_at = time.perf_counter()
    logger.info("Field agent run started history_messages=%d", len(messages))
    graph = get_field_builder_graph()
    result = graph.invoke({"prompt": prompt, "messages": messages, "spec_context": "", "draft": {}, "assistant_message": "", "field_context": field_context})
    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info("Field agent run completed duration_ms=%.0f", duration_ms)
    return result
