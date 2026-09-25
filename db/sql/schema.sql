-- 1. Atomic Field Templates Library
CREATE TABLE field_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    label VARCHAR(255) NOT NULL,
    field_type VARCHAR(50) NOT NULL, -- text, select, autocomplete, date, checkbox
    angular_config JSONB NOT NULL,   -- Maps to Angular Material spec
    validation_rules JSONB NOT NULL, -- { "required": true, "minlength": 2 }
    validation_messages JSONB NOT NULL DEFAULT '{}'::jsonb, -- Human-readable messages keyed by validation rule
    api_config JSONB NULL,           -- Stores endpoint & debounce rules for typeahead fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Mini-Form Metadata Container
CREATE TABLE form_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Version Control & Release Lifecycle (Immutable when Published)
CREATE TABLE form_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID REFERENCES form_definitions(id) ON DELETE CASCADE,
    version_number VARCHAR(20) NOT NULL, -- e.g., "1.0.0"
    status VARCHAR(20) NOT NULL DEFAULT 'draft', -- 'draft', 'published', 'archived'
    layout_tree JSONB NOT NULL, -- Stores grid spans, order, and field references
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(form_id, version_number)
);

