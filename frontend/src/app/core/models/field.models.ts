export interface FieldTemplate {
  id?: string;
  name: string;
  label: string;
  field_type: string;
  angular_config: Record<string, unknown>;
  validation_rules: Record<string, unknown>;
  validation_messages: Record<string, string>;
  api_config: Record<string, unknown> | null;
  assistant_message?: string;
}

export interface FieldGenerateResponse extends FieldTemplate {}
