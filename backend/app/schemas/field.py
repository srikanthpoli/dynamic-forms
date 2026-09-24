from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class FieldGenerateRequest(BaseModel):
    session_id: str
    prompt: str
    field_context: dict[str, Any] | None = None

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "session_id": "test-session-001",
            "prompt": "Create a required full name text field with a maximum length of 100 characters",
            "field_context": None,
        }]
    })


class FieldDraftResponse(BaseModel):
    name: str
    label: str
    field_type: str
    angular_config: dict[str, Any]
    validation_rules: dict[str, Any]
    validation_messages: dict[str, str]
    api_config: dict[str, Any] | None = None
    assistant_message: str

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "name": "customer_full_name",
            "label": "Customer Full Name",
            "field_type": "text",
            "angular_config": {
                "angular_tag": "mat-form-field",
                "inner_element": "input matInput",
            },
            "validation_rules": {
                "required": True,
                "maxlength": 100,
            },
            "validation_messages": {
                "required": "Customer Full Name is required.",
                "maxlength": "Customer Full Name must be 100 characters or fewer.",
            },
            "api_config": None,
            "assistant_message": "Created a required Customer Full Name text field with a maximum length of 100 characters.",
        }]
    })


class FieldPublishRequest(BaseModel):
    name: str
    label: str
    field_type: str
    angular_config: dict[str, Any]
    validation_rules: dict[str, Any]
    validation_messages: dict[str, str]
    api_config: dict[str, Any] | None = None

    model_config = ConfigDict(extra="ignore", json_schema_extra={
        "examples": [{
            "name": "customer_full_name_test",
            "label": "Customer Full Name",
            "field_type": "text",
            "angular_config": {
                "angular_tag": "mat-form-field",
                "inner_element": "input matInput",
            },
            "validation_rules": {
                "required": True,
                "maxlength": 100,
            },
            "validation_messages": {
                "required": "Customer Full Name is required.",
                "maxlength": "Customer Full Name must be 100 characters or fewer.",
            },
            "api_config": None,
        }]
    })


class FieldOverrideRequest(BaseModel):
    name: str
    label: str
    field_type: str
    angular_config: dict[str, Any]
    validation_rules: dict[str, Any]
    validation_messages: dict[str, str]
    api_config: dict[str, Any] | None = None

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "name": "full_name",
            "label": "Full Name",
            "field_type": "text",
            "angular_config": {
                "angular_tag": "mat-form-field",
                "inner_element": "input matInput",
            },
            "validation_rules": {
                "required": True,
                "maxlength": 200,
            },
            "validation_messages": {
                "required": "Full Name is required.",
                "maxlength": "Full Name must be 200 characters or fewer.",
            },
            "api_config": None,
        }]
    })


class FieldTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    label: str
    field_type: str
    angular_config: dict[str, Any]
    validation_rules: dict[str, Any]
    validation_messages: dict[str, str]
    api_config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def fill_legacy_validation_messages(self):
        if self.validation_messages:
            return self
        label = self.label
        messages: dict[str, str] = {}
        for name, value in self.validation_rules.items():
            if name == "required":
                messages[name] = f"{label} is required."
            elif name == "requiredTrue":
                messages[name] = f"{label} must be accepted."
            elif name == "email":
                messages[name] = f"{label} must be a valid email address."
            elif name == "minlength":
                messages[name] = f"{label} must contain at least {value} characters."
            elif name == "maxlength":
                messages[name] = f"{label} must contain no more than {value} characters."
            elif name == "min":
                messages[name] = f"{label} must be at least {value}."
            elif name == "max":
                messages[name] = f"{label} must be no more than {value}."
            elif name == "pattern":
                messages[name] = f"{label} must match the required format."
            else:
                messages[name] = f"{label} must satisfy the {name} rule."
        self.validation_messages = messages
        return self
