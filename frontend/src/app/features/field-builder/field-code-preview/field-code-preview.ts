import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { FieldTemplate } from '../../../core/models/field.models';
import { getAngularValidatorsCode } from '../../../core/validation/field-validation';
import { generateAngularMaterialTemplate, getAngularMaterialImports } from '../../../core/code-generation/angular-material-field-code';

@Component({
  selector: 'app-field-code-preview',
  standalone: true,
  templateUrl: './field-code-preview.html',
  styleUrl: './field-code-preview.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldCodePreviewComponent {
  @Input() field: FieldTemplate | null = null;

  get htmlCode(): string {
    if (!this.field) return '';
    const control = this.controlName;
    return generateAngularMaterialTemplate(this.field, control);
  }

  get typescriptCode(): string {
    if (!this.field) return '';
    const validators = this.validatorCode;
    return `readonly form = this.formBuilder.group({\n  ${this.controlName}: ['', ${validators}],\n});`;
  }

  get importsCode(): string {
    if (!this.field) return '';
    return getAngularMaterialImports(this.field);
  }

  private get controlName(): string {
    return this.field?.name?.replace(/[^a-zA-Z0-9_$]/g, '_') || 'fieldValue';
  }

  private get validatorCode(): string {
    return getAngularValidatorsCode(this.field?.validation_rules ?? {});
  }
}
