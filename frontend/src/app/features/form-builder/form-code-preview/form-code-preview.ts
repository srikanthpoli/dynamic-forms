import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { FormDefinitionJson } from '../../../core/models/form.models';
import { getAngularValidatorsCode } from '../../../core/validation/field-validation';
import { generateAngularMaterialTemplate, getAngularMaterialImports } from '../../../core/code-generation/angular-material-field-code';

@Component({
  selector: 'app-form-code-preview',
  standalone: true,
  templateUrl: './form-code-preview.html',
  styleUrl: './form-code-preview.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FormCodePreviewComponent {
  @Input() form: FormDefinitionJson | null = null;

  private get sortedLayout() {
    return [...(this.form?.layout_tree ?? [])].sort((a, b) => a.order - b.order);
  }

  private controlName(name: string | undefined, fallback: string): string {
    return name?.replace(/[^a-zA-Z0-9_$]/g, '_') || fallback;
  }

  get htmlCode(): string {
    if (!this.form) return '';
    const rows = this.sortedLayout.map((node, index) => {
      if (!node.field) return `<!-- Unknown field: ${node.field_id} -->`;
      const control = this.controlName(node.field.name, `field_${index}`);
      const markup = generateAngularMaterialTemplate(node.field, control);
      return markup.split('\n').map(line => `  ${line}`).join('\n');
    });
    return `<form [formGroup]="form" (ngSubmit)="onSubmit()">\n${rows.join('\n\n')}\n\n  <button mat-flat-button color="primary" type="submit" [disabled]="form.invalid">Submit</button>\n</form>`;
  }

  get typescriptCode(): string {
    if (!this.form) return '';
    const controls = this.sortedLayout.map((node, index) => {
      if (!node.field) return null;
      const control = this.controlName(node.field.name, `field_${index}`);
      const validators = getAngularValidatorsCode(node.field.validation_rules ?? {});
      return `  ${control}: ['', ${validators}],`;
    }).filter((line): line is string => line !== null);

    return `import { Validators } from '@angular/forms';\n\nreadonly form = this.formBuilder.group({\n${controls.join('\n')}\n});\n\nonSubmit(): void {\n  if (this.form.invalid) return;\n  console.log(this.form.value);\n}`;
  }

  get importsCode(): string {
    if (!this.form) return '';
    const modules = new Set<string>();
    for (const node of this.sortedLayout) {
      if (!node.field) continue;
      for (const module of getAngularMaterialImports(node.field).replace(/^imports: \[|\]$/g, '').split(', ')) {
        modules.add(module);
      }
    }
    modules.add('MatButtonModule');
    return `imports: [${Array.from(modules).join(', ')}]`;
  }
}
