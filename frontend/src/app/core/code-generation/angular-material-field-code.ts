import { FieldTemplate } from '../models/field.models';
import { CONTROL_MODULES, ControlKind, resolveControlKind } from '../capabilities/control-registry';

type FieldCodeRenderer = (field: FieldTemplate, controlName: string) => string;

const kindRenderers: Partial<Record<ControlKind, FieldCodeRenderer>> = {
  select: (field, control) => `<mat-form-field appearance="fill">\n  <mat-label>${field.label}</mat-label>\n  <mat-select formControlName="${control}">\n    @for (option of ${control}Options; track option.value) {\n      <mat-option [value]="option.value">{{ option.label }}</mat-option>\n    }\n  </mat-select>\n</mat-form-field>`,
  checkbox: (field, control) => `<mat-checkbox formControlName="${control}">${field.label}</mat-checkbox>`,
  radio: (field, control) => `<mat-radio-group formControlName="${control}">\n  @for (option of ${control}Options; track option.value) {\n    <mat-radio-button [value]="option.value">{{ option.label }}</mat-radio-button>\n  }\n</mat-radio-group>`,
  autocomplete: (field, control) => `<mat-form-field appearance="fill">\n  <mat-label>${field.label}</mat-label>\n  <input matInput formControlName="${control}" [matAutocomplete]="${control}Auto">\n  <mat-autocomplete #${control}Auto="matAutocomplete">\n    @for (option of ${control}Options$ | async; track option.value) {\n      <mat-option [value]="option.value">{{ option.label }}</mat-option>\n    }\n  </mat-autocomplete>\n</mat-form-field>`,
};

export function generateAngularMaterialTemplate(field: FieldTemplate, controlName: string): string {
  const renderer = kindRenderers[resolveControlKind(field.field_type)];
  if (renderer) return renderer(field, controlName);

  const inputType = field.validation_rules?.['email'] ? 'email' : field.field_type || 'text';
  const required = field.validation_rules?.['required'] ? ' required' : '';
  const maxLength = typeof field.validation_rules?.['maxlength'] === 'number'
    ? ` maxlength="${field.validation_rules['maxlength']}"`
    : '';
  const element = typeof field.angular_config?.['inner_element'] === 'string'
    ? field.angular_config['inner_element']
    : 'input matInput';

  const control = element.startsWith('input')
    ? `<input matInput type="${inputType}" formControlName="${controlName}"${required}${maxLength}>`
    : `<${element} formControlName="${controlName}"${required}${maxLength}></${element.split(' ')[0]}>`;
  return `<mat-form-field appearance="fill">\n  <mat-label>${field.label}</mat-label>\n  ${control}\n</mat-form-field>`;
}

export function getAngularMaterialImports(field: FieldTemplate): string {
  const modules = new Set(['ReactiveFormsModule']);
  for (const module of CONTROL_MODULES[resolveControlKind(field.field_type)]) modules.add(module);
  return `imports: [${Array.from(modules).join(', ')}]`;
}
