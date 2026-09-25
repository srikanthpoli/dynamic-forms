"""SQLAlchemy models mirroring db/sql/schema.sql."""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class FieldTemplate(Base):
    __tablename__ = "field_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    label = Column(String(255), nullable=False)
    field_type = Column(String(50), nullable=False)
    angular_config = Column(JSONB, nullable=False)
    validation_rules = Column(JSONB, nullable=False)
    validation_messages = Column(JSONB, nullable=False, default=dict, server_default="{}")
    api_config = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FormDefinition(Base):
    __tablename__ = "form_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FormVersion(Base):
    __tablename__ = "form_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id = Column(UUID(as_uuid=True), ForeignKey("form_definitions.id", ondelete="CASCADE"))
    version_number = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    layout_tree = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IrForm(Base):
    __tablename__ = "ir_forms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ir_id = Column(UUID(as_uuid=True), ForeignKey("tps_irmain.id", ondelete="CASCADE"), nullable=False)
    form_id = Column(UUID(as_uuid=True), ForeignKey("form_definitions.id"), nullable=False)
    form_version_id = Column(UUID(as_uuid=True), ForeignKey("form_versions.id"), nullable=False)
    status = Column(String(30), nullable=False, default="assigned")
    required = Column(Boolean, nullable=False, default=False)
    display_order = Column(Integer, nullable=False, default=0)
    released_at = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TpsIrMain(Base):
    __tablename__ = "tps_irmain"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ir_number = Column(String(50), unique=True, nullable=False)
    customer_name = Column(String(255), nullable=False)
    uen = Column(String(50), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    tin = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft")
    priority = Column(String(20), nullable=False, default="normal")
    onboarding_type = Column(String(100), nullable=True)
    risk_rating = Column(String(30), nullable=True)
    sales_user_id = Column(UUID(as_uuid=True), nullable=True)
    notes = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ir_id = Column(UUID(as_uuid=True), ForeignKey("tps_irmain.id", ondelete="SET NULL"), nullable=True)
    submission_number = Column(String(80), unique=True, nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    form_snapshot = Column(JSONB, nullable=False)
    submission_data = Column(JSONB, nullable=False, default=dict)
    submitted_by = Column(String(255), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SubmissionEvent(Base):
    __tablename__ = "submission_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("form_submissions.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    actor_type = Column(String(30), nullable=False)
    actor_id = Column(String(255), nullable=True)
    details = Column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
