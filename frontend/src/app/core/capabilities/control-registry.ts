/**
 * Single source of truth mapping a field's `field_type` to a rendering "kind".
 * Live preview, codegen, and (future) any other consumer resolve through here
 * so new field_type names that reuse an existing Material control need only
 * an alias entry below, not new template/switch code.
 */
export type ControlKind = 'text-like' | 'select' | 'checkbox' | 'radio' | 'autocomplete';

const FIELD_TYPE_ALIASES: Record<string, ControlKind> = {
  select: 'select',
  dropdown: 'select',
  'multi-select': 'select',
  'single-select': 'select',
  checkbox: 'checkbox',
  toggle: 'checkbox',
  radio: 'radio',
  'yes-no': 'radio',
  autocomplete: 'autocomplete',
};

export function resolveControlKind(fieldType: string | undefined | null): ControlKind {
  return FIELD_TYPE_ALIASES[fieldType ?? ''] ?? 'text-like';
}

export const CONTROL_MODULES: Record<ControlKind, string[]> = {
  'text-like': ['MatFormFieldModule', 'MatInputModule'],
  select: ['MatFormFieldModule', 'MatSelectModule'],
  checkbox: ['MatCheckboxModule'],
  radio: ['MatRadioModule'],
  autocomplete: ['MatFormFieldModule', 'MatInputModule', 'MatAutocompleteModule'],
};
