"""In-memory per-session state for the Field and Form Builder Agents.

Dev-only: cleared when the backend restarts. A DELETE /api/fields/sessions/{id}
endpoint ("kill session") lets the frontend explicitly clear a session's
conversation history and pending draft.
"""

from typing import TypedDict

from langchain_core.messages import BaseMessage


class FieldSession(TypedDict):
    messages: list[BaseMessage]
    draft: dict | None


class FormSession(TypedDict):
    messages: list[BaseMessage]
    layout_tree: list[dict]
    form_definition: dict


class TpsIrSession(TypedDict):
    messages: list[BaseMessage]
    ir_context: dict | None
    pending_form: dict | None


_SESSIONS: dict[str, FieldSession] = {}
_FORM_SESSIONS: dict[str, FormSession] = {}
_TPS_IR_SESSIONS: dict[str, TpsIrSession] = {}


def get_session(session_id: str) -> FieldSession:
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = {"messages": [], "draft": None}
    return _SESSIONS[session_id]


def save_session(session_id: str, session: FieldSession) -> None:
    _SESSIONS[session_id] = session


def kill_session(session_id: str) -> bool:
    return _SESSIONS.pop(session_id, None) is not None


def get_form_session(session_id: str) -> FormSession:
    if session_id not in _FORM_SESSIONS:
        _FORM_SESSIONS[session_id] = {
            "messages": [],
            "layout_tree": [],
            "form_definition": {},
        }
    return _FORM_SESSIONS[session_id]


def save_form_session(session_id: str, session: FormSession) -> None:
    _FORM_SESSIONS[session_id] = session


def kill_form_session(session_id: str) -> bool:
    return _FORM_SESSIONS.pop(session_id, None) is not None


def get_tps_ir_session(session_id: str) -> TpsIrSession:
    if session_id not in _TPS_IR_SESSIONS:
        _TPS_IR_SESSIONS[session_id] = {"messages": [], "ir_context": None, "pending_form": None}
    else:
        _TPS_IR_SESSIONS[session_id].setdefault("pending_form", None)
    return _TPS_IR_SESSIONS[session_id]


def save_tps_ir_session(session_id: str, session: TpsIrSession) -> None:
    _TPS_IR_SESSIONS[session_id] = session


def kill_tps_ir_session(session_id: str) -> bool:
    return _TPS_IR_SESSIONS.pop(session_id, None) is not None


def clear_all_sessions() -> dict[str, int]:
    field_count = len(_SESSIONS)
    form_count = len(_FORM_SESSIONS)
    tps_count = len(_TPS_IR_SESSIONS)
    _SESSIONS.clear()
    _FORM_SESSIONS.clear()
    _TPS_IR_SESSIONS.clear()
    return {"field_sessions": field_count, "form_sessions": form_count, "tps_ir_sessions": tps_count}
