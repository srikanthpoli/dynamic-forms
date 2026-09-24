import { FieldTemplate } from './field.models';

export interface FormLayoutNode {
  field_id: string;
  order: number;
  column_span?: number | null;
  field?: FieldTemplate | null;
}

export interface FormDefinitionJson {
  title: string;
  description?: string | null;
  layout_tree: FormLayoutNode[];
}

export interface FormBuildResponse {
  session_id: string;
  form_definition: FormDefinitionJson;
  assistant_message?: string | null;
}

export interface FormDefinition {
  id: string;
  title: string;
  description?: string | null;
}

export interface PublishedForm {
  form_id: string;
  title: string;
  description?: string | null;
  version_id: string;
  version_number: string;
  layout_tree: FormLayoutNode[];
}

export interface FormVersion {
  id: string;
  form_id: string;
  version_number: string;
  status: 'draft' | 'published' | 'archived';
  layout_tree: FormLayoutNode[];
}
