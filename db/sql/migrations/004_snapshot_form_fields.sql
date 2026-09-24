-- Replace legacy field_id-only form nodes with immutable field snapshots.
UPDATE form_versions AS version
SET layout_tree = snapshots.layout_tree
FROM (
    SELECT
        version_id,
        jsonb_agg(
            CASE
                WHEN node ? 'field' THEN node
                WHEN field.id IS NULL THEN node
                ELSE (node - 'field_id') || jsonb_build_object(
                    'field', jsonb_build_object(
                        'id', field.id::text,
                        'name', field.name,
                        'label', field.label,
                        'field_type', field.field_type,
                        'angular_config', field.angular_config,
                        'validation_rules', field.validation_rules,
                        'validation_messages', field.validation_messages,
                        'api_config', field.api_config
                    )
                )
            END
            ORDER BY COALESCE((node->>'order')::integer, 0)
        ) AS layout_tree
    FROM (
        SELECT id AS version_id, jsonb_array_elements(layout_tree) AS node
        FROM form_versions
    ) AS nodes
    LEFT JOIN field_templates AS field
        ON field.id::text = nodes.node->>'field_id'
    GROUP BY version_id
) AS snapshots
WHERE version.id = snapshots.version_id;
