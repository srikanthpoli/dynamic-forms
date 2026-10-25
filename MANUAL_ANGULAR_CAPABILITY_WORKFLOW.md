# Manually Adding an Angular Material Capability

This guide covers the manual-first workflow: a developer edits `backend/app/data/angular_material_capabilities.json`, refreshes the backend capability index, and implements the matching frontend control.

The capability JSON teaches the Field Builder AI what a component supports. It does **not** implement the Angular UI by itself.

## Example: Date Picker

### 1. Add the capability to the JSON file

In `backend/app/data/angular_material_capabilities.json`, add a new object to `supported_fields`:

```json
{
  "type": "date",
  "angular_tag": "mat-form-field",
  "inner_element": "input matInput [matDatepicker]",
  "module": "MatDatepickerModule",
  "allowed_inputs": ["matInput", "matDatepicker"],
  "allowed_outputs": ["dateChange"],
  "allowed_validations": ["required"],
  "required_options": [],
  "documentation_url": "https://material.angular.dev/components/datepicker/overview"
}
```

Keep the JSON valid and make the component's type and API details match the Angular Material version used by the frontend.

### 2. Refresh the capability search index

The Field Builder retrieves capability information from Chroma. After editing the JSON, rebuild that index from the file:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/spec/refresh
```

This endpoint calls `build_or_refresh_index()`, which reads the configured capability JSON and rebuilds the `angular_material_spec` collection.

For this manual-first workflow, do **not** call `POST /api/spec/generate-capabilities`. That endpoint fetches documentation, asks the LLM to generate a registry, and writes the generated result over the JSON file. `POST /api/spec/refresh-all-indexes` also reads the manual JSON, but additionally rebuilds the published-fields and published-forms indexes; use it only when those indexes need refreshing too.

`backend/app/capabilities/generator.py` does not need changes when the JSON is manually maintained.

### 3. Register the frontend control kind

In `frontend/src/app/core/capabilities/control-registry.ts`, add a new kind, aliases, and required Material modules:

```ts
export type ControlKind =
  | 'text-like'
  | 'select'
  | 'checkbox'
  | 'radio'
  | 'autocomplete'
  | 'date';

const FIELD_TYPE_ALIASES: Record<string, ControlKind> = {
  // Keep existing aliases.
  date: 'date',
  'date-picker': 'date',
};

export const CONTROL_MODULES: Record<ControlKind, string[]> = {
  // Keep existing entries.
  date: [
    'MatFormFieldModule',
    'MatInputModule',
    'MatDatepickerModule',
    'MatNativeDateModule',
  ],
};
```

The form-field and input modules are included because the datepicker example uses a Material form field and input. If the component uses different modules, register the modules it actually needs.

### 4. Render it in the live preview

In `frontend/src/app/features/field-builder/field-live-preview/field-live-preview.ts`:

- Import `MatDatepickerModule` from `@angular/material/datepicker`.
- Import `MatNativeDateModule` from `@angular/material/core`.
- Add both modules to the standalone component's `imports`.
- Ensure the control can hold a `Date` internally and that input/output values are converted consistently.

Example date case for `frontend/src/app/features/field-builder/field-live-preview/field-live-preview.html`:

```html
@case ('date') {
  <mat-form-field appearance="fill" class="control">
    <mat-label>{{ field.label }}</mat-label>
    <input matInput [matDatepicker]="picker" [formControl]="previewControl" />
    <mat-datepicker-toggle matIconSuffix [for]="picker" />
    <mat-datepicker #picker />
    @if (previewControl.invalid && previewControl.touched) {
      <mat-error>{{ validationMessage }}</mat-error>
    }
  </mat-form-field>
}
```

Prefer storing date-only values as `YYYY-MM-DD` strings in form submissions. Convert to a local `Date` for the Material control and back to the same date string when emitting a value. Avoid `toISOString()` for date-only values because UTC conversion can change the calendar day.

The Form Builder preview embeds this live-preview component. If another runtime screen has its own field renderer, add the equivalent date case there too.

### 5. Generate Angular code for it

In `frontend/src/app/core/code-generation/angular-material-field-code.ts`, add a `date` renderer to `kindRenderers`:

```ts
date: (field, control) =>
  `<mat-form-field appearance="fill">\n  <mat-label>${field.label}</mat-label>\n  <input matInput [matDatepicker]="${control}Picker" formControlName="${control}">\n  <mat-datepicker-toggle matIconSuffix [for]="${control}Picker"></mat-datepicker-toggle>\n  <mat-datepicker #${control}Picker></mat-datepicker>\n</mat-form-field>`,
```

Generated module imports are gathered from `CONTROL_MODULES`, so keep that mapping in sync with the renderer.

### 6. Add validation only when needed

`required` is already supported. Add a rule in `frontend/src/app/core/validation/field-validation.ts` only when this component needs validation that does not already exist. The current `min` and `max` validators are numeric; do not use them for date boundaries without implementing date-aware validation.

### 7. Test the complete path

Test that:

- The backend registry contains the new field and `/api/spec/refresh` indexes it.
- The frontend resolves `date` to the `date` control kind.
- The live preview renders and updates the Date Picker value correctly.
- Generated code includes the picker and its required imports.
- Any supported date validations report the expected errors.

No database migration is needed: field types are stored as strings and field definitions are stored in JSON. Adding an alias for a name that maps to an existing control kind can require only a registry alias; a genuinely new UI control requires the rendering and code-generation work above.
