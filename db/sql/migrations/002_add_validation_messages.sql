ALTER TABLE field_templates
ADD COLUMN IF NOT EXISTS validation_messages JSONB NOT NULL DEFAULT '{}'::jsonb;