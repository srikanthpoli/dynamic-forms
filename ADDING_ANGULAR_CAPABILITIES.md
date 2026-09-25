# Adding a new Angular Material capability

`field_type` is a free-form string (no backend enum/migration needed). Rendering
and codegen resolve through one shared registry —
`frontend/src/app/core/capabilities/control-registry.ts` — which maps a
`field_type` to a `ControlKind` (`text-like` | `select` | `checkbox` | `radio` |
`autocomplete`). **If the LLM generates a new `field_type` name that reuses an
existing Material control (e.g. "dropdown", "yes-no"), just add it to
`FIELD_TYPE_ALIASES` in that one file — no other changes needed.**

Adding a genuinely new UI pattern (a `ControlKind` that doesn't exist yet, e.g.
datepicker, slider) still touches the capability registry and rendering
pipeline. Checklist:

Worked example below: adding a **date** field type backed by `MatDatepickerModule`.

## 1. Backend capability registry
`backend/app/capabilities/generator.py`
- Add the component to `OFFICIAL_DOCS` — key + official Angular Material doc URL.
- Add matching defaults to `COMPONENT_DEFAULTS` — `angular_tag`, `inner_element`, `module`.
- Re-run `POST /api/spec/generate-capabilities` (or `/api/spec/refresh-all-indexes`)
  so the doc is scraped, the registry regenerated, and re-embedded into the
  `angular_material_spec` Chroma collection. Skipping this means the Field
  Builder agent will never know the component exists.

```python
OFFICIAL_DOCS = {
    "text": "https://material.angular.dev/components/input/overview",
    "date": "https://material.angular.dev/components/datepicker/overview",
    ...
}

COMPONENT_DEFAULTS = {
    "date": {
        "angular_tag": "mat-form-field",
        "inner_element": "input matInput [matDatepicker]",
        "module": "MatDatepickerModule",
    },
    ...
}
```

## 2. Shared control registry
`frontend/src/app/core/capabilities/control-registry.ts`
- Add `'date'` to `ControlKind`.
- Add the `date` → `'date'` entry to `FIELD_TYPE_ALIASES` (plus any name variants
  the LLM might generate, e.g. `"date-picker"`).
- Add `date: ['MatDatepickerModule', 'MatNativeDateModule']` to `CONTROL_MODULES`.

```ts
export type ControlKind = 'text-like' | 'select' | 'checkbox' | 'radio' | 'autocomplete' | 'date';

const FIELD_TYPE_ALIASES: Record<string, ControlKind> = {
  ...
  date: 'date',
  'date-picker': 'date',
};

export const CONTROL_MODULES: Record<ControlKind, string[]> = {
  ...
  date: ['MatDatepickerModule', 'MatNativeDateModule'],
};
```

## 3. Frontend live preview
`frontend/src/app/features/field-builder/field-live-preview/field-live-preview.html`
- Add a `@case ('date')` (the switch now runs on `controlKind`, resolved from the
  registry above) rendering the actual Material control.

```html
@case ('date') {
  <mat-form-field appearance="fill" class="control">
    <mat-label>{{ field.label }}</mat-label>
    <input matInput [matDatepicker]="picker" [formControl]="previewControl">
    <mat-datepicker-toggle matIconSuffix [for]="picker"></mat-datepicker-toggle>
    <mat-datepicker #picker></mat-datepicker>
    @if (previewControl.invalid && previewControl.touched) { <mat-error>{{ validationMessage }}</mat-error> }
  </mat-form-field>
}
```

`frontend/src/app/features/field-builder/field-live-preview/field-live-preview.ts`
- If the value isn't a simple string/boolean (date object, array for
  multi-select, etc.), extend `previewControl`/`valueChange`/`initialValue` typing.
- Import the needed Material module (e.g. `MatDatepickerModule`) into the
  component's standalone `imports: []`.

```ts
@Input() initialValue: string | boolean | Date | null = null;
@Output() readonly valueChange = new EventEmitter<string | boolean | Date>();
previewControl = new FormControl<string | boolean | Date>('', { nonNullable: true });

@Component({
  imports: [FormsModule, ReactiveFormsModule, MatDatepickerModule, MatNativeDateModule, /* ...existing */],
  ...
})
```

## 4. Frontend code generation
`frontend/src/app/core/code-generation/angular-material-field-code.ts`
- Add a `date` entry to `kindRenderers` — the generated Angular template
  snippet for forms built with this field. Module imports are already handled
  dynamically via `CONTROL_MODULES` from the shared registry — no separate map to update.

```ts
const kindRenderers: Partial<Record<ControlKind, FieldCodeRenderer>> = {
  ...
  date: (field, control) => `<mat-form-field appearance="fill">\n  <mat-label>${field.label}</mat-label>\n  <input matInput [matDatepicker]="${control}Picker" formControlName="${control}">\n  <mat-datepicker-toggle matIconSuffix [for]="${control}Picker"></mat-datepicker-toggle>\n  <mat-datepicker #${control}Picker></mat-datepicker>\n</mat-form-field>`,
};
```

## 5. Validation
`frontend/src/app/core/validation/field-validation.ts`
- Only if the new component needs a rule not already in `ruleDefinitions`
  (required, requiredTrue, email, minlength, maxlength, min, max, pattern).
  Add a new entry with `create` + `message`.

```ts
const ruleDefinitions: Record<string, ValidationRuleDefinition> = {
  ...
  minDate: {
    create: value => (control => {
      const date = control.value ? new Date(control.value) : null;
      return date && date < new Date(value as string) ? { minDate: { min: value } } : null;
    }) as ValidatorFn,
    message: error => `Choose a date on or after ${error['min']}.`,
  },
};
```

## 6. No changes needed
- DB/schemas/form snapshots store `field_type` as a plain string — e.g. a
  saved date field is just `{ "field_type": "date", "validation_rules": { "minDate": "2026-01-01" } }`.
- Display-only surfaces (field-library, published-library, field-preview
  summary cards) already render `field_type` as text, so `"date"` shows up
  automatically with no code change.
- Any new `field_type` name that maps to an *existing* `ControlKind` (step 2
  alias only) needs no preview/codegen/validation changes at all.
