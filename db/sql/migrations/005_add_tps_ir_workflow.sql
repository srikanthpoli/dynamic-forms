-- TPS Implementation Request workflow.
-- Run after schema.sql and migrations 002-004 on a database where these
-- workflow tables do not already exist.

CREATE TABLE tps_irmain (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ir_number VARCHAR(50) UNIQUE NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    uen VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    tin VARCHAR(50),
    address TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    onboarding_type VARCHAR(100),
    risk_rating VARCHAR(30),
    sales_user_id UUID,
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ir_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ir_id UUID NOT NULL REFERENCES tps_irmain(id) ON DELETE CASCADE,
    form_id UUID NOT NULL REFERENCES form_definitions(id),
    form_version_id UUID NOT NULL REFERENCES form_versions(id),
    status VARCHAR(30) NOT NULL DEFAULT 'assigned',
    required BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 0,
    released_at TIMESTAMP WITH TIME ZONE,
    due_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ir_id, form_id)
);

CREATE TABLE form_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ir_id UUID REFERENCES tps_irmain(id) ON DELETE SET NULL,
    submission_number VARCHAR(80) UNIQUE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    form_snapshot JSONB NOT NULL,
    submission_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_by VARCHAR(255),
    submitted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE submission_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES form_submissions(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    form_snapshot JSONB NOT NULL,
    submission_data JSONB NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(submission_id, revision_number)
);

CREATE TABLE submission_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES form_submissions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    actor_type VARCHAR(30) NOT NULL,
    actor_id VARCHAR(255),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
