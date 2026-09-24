"""SQLAlchemy models mirroring db/sql/schema.sql."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
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


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id = Column(UUID(as_uuid=True), ForeignKey("form_definitions.id"))
    version_id = Column(UUID(as_uuid=True), ForeignKey("form_versions.id"))
    submission_data = Column(JSONB, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
