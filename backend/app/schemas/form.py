from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FormBuildRequest(BaseModel):
    session_id: str
    prompt: str
    form_context: dict[str, Any] | None = None

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "session_id": "form-session-001",
            "prompt": "Build a customer registration form using the available full name field",
            "form_context": None,
        }]
    })


class FormBuildResponse(BaseModel):
    session_id: str
    form_definition: dict[str, Any]
    assistant_message: str | None = None


class TpsIrOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ir_number: str
    customer_name: str
    uen: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    tin: str | None = None
    address: str | None = None
    status: str
    priority: str
    onboarding_type: str | None = None
    risk_rating: str | None = None

    class TpsIrUpdate(BaseModel):
        """Editable fields for PUT /api/tps/irs/{ir_number}."""

        customer_name: str
        uen: str | None = None
        first_name: str | None = None
        last_name: str | None = None
        tin: str | None = None
        address: str | None = None
        status: str = "draft"
        priority: str = "normal"
        onboarding_type: str | None = None
        risk_rating: str | None = None


class TpsIrUpdate(BaseModel):
    """Editable fields for PUT /api/tps/irs/{ir_number}."""

    customer_name: str
    uen: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    tin: str | None = None
    address: str | None = None
    status: str = "draft"
    priority: str = "normal"
    onboarding_type: str | None = None
    risk_rating: str | None = None

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "customer_name": "Northstar Trading Pte Ltd",
            "uen": "201912345K",
            "first_name": "Alicia",
            "last_name": "Tan",
            "tin": "T1234567A",
            "address": "12 Marina View, Singapore",
            "status": "active",
            "priority": "high",
            "onboarding_type": "Commercial onboarding",
            "risk_rating": "medium",
        }]
    })


class TpsIrAssistRequest(BaseModel):
    session_id: str
    prompt: str
    ir_context: TpsIrOut | None = None


class TpsIrContextRequest(BaseModel):
    session_id: str
    ir_context: TpsIrOut


class TpsIrAssistResponse(BaseModel):
    assistant_message: str
    published_forms: list[dict[str, Any]] = []
    pending_form: dict[str, Any] | None = None


class TpsFormCandidate(BaseModel):
    form_id: UUID
    version_id: UUID
    title: str
    version_number: str
    match_summary: str


class TpsFormSearchResponse(BaseModel):
    status: str
    forms: list[TpsFormCandidate] = []
    assistant_message: str


class IrFormCreate(BaseModel):
    form_id: UUID
    form_version_id: UUID
    required: bool = False
    display_order: int = 0


class IrFormOut(BaseModel):
    id: UUID
    ir_id: UUID
    form_id: UUID
    form_version_id: UUID
    form_title: str
    version_number: str
    status: str
    required: bool
    display_order: int
    released_at: Any | None = None
    submission_id: UUID | None = None
    form_snapshot: dict[str, Any] | None = None
    submission_data: dict[str, Any] | None = None
    event_history: list[dict[str, Any]] = []


class TpsReleaseOut(BaseModel):
    ir_form_id: UUID
    submission_id: UUID
    status: str


class SubmissionDataUpdate(BaseModel):
    submission_data: dict[str, Any]


class PublishedFormOut(BaseModel):
    form_id: UUID
    title: str
    description: str | None = None
    version_id: UUID
    version_number: str
    layout_tree: list[dict[str, Any]]


class FormDefinitionCreate(BaseModel):
    title: str
    description: str | None = None

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "title": "Customer Registration",
            "description": "Customer onboarding form",
        }]
    })


class FormDefinitionUpdate(FormDefinitionCreate):
    pass


class FormDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None


class FormVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    form_id: UUID
    version_number: str
    status: str
    layout_tree: list[dict[str, Any]]


class FormSubmissionCreate(BaseModel):
    version_id: UUID
    submission_data: dict[str, Any]

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "version_id": "00000000-0000-0000-0000-000000000000",
            "submission_data": {
                "fullName": "Jane Doe",
                "email": "jane@example.com",
            },
        }]
    })


class FormSubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    form_id: UUID
    version_id: UUID
    submission_data: dict[str, Any]


class LayoutNode(BaseModel):
    field_id: str
    order: int
    column_span: int | None = 12


class FormVersionCreate(BaseModel):
    version_number: str | None = None
    version_bump: Literal["major", "minor", "patch"] = "patch"
    layout_tree: list[LayoutNode]

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "version_bump": "patch",
            "layout_tree": [{
                "field_id": "00000000-0000-0000-0000-000000000000",
                "order": 0,
                "column_span": 12,
            }],
        }]
    })


class FormDefinitionVersionCreate(BaseModel):
    version_number: str | None = None
    version_bump: Literal["major", "minor", "patch"] = "patch"
    form_definition: dict[str, Any]

    model_config = ConfigDict(extra="ignore", json_schema_extra={
        "examples": [{
            "version_bump": "patch",
            "form_definition": {
                "title": "Customer Registration",
                "description": "Customer onboarding form",
                "layout_tree": [{
                    "field_id": "PASTE-PUBLISHED-FIELD-ID-HERE",
                    "order": 0,
                    "column_span": 12,
                }],
            },
        }]
    })


class FormDefinitionVersionUpdate(BaseModel):
    form_definition: dict[str, Any]

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "form_definition": {
                "title": "Customer Registration",
                "description": "Updated customer onboarding form",
                "layout_tree": [{
                    "field_id": "PASTE-PUBLISHED-FIELD-ID-HERE",
                    "order": 0,
                    "column_span": 6,
                }],
            }
        }]
    })
