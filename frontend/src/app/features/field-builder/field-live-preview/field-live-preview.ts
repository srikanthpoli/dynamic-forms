import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';
import { MatSelectModule } from '@angular/material/select';
import { FieldTemplate } from '../../../core/models/field.models';
import { resolveControlKind } from '../../../core/capabilities/control-registry';
import { buildFieldValidators, getConfiguredValidationMessages, getValidationMessage } from '../../../core/validation/field-validation';

@Component({
  selector: 'app-field-live-preview',
  standalone: true,
  imports: [FormsModule, ReactiveFormsModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatRadioModule, MatSelectModule],
  templateUrl: './field-live-preview.html',
  styleUrl: './field-live-preview.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldLivePreviewComponent implements OnInit, OnChanges {
  @Input() field: FieldTemplate | null = null;
  /** Hides the standalone "Field Preview" label and rule tiles when embedded inside a real form. */
  @Input() compact = false;
  /** Seeds the control with a previously saved value (e.g. a draft submission). */
  @Input() initialValue: string | boolean | null = null;
  @Output() readonly validityChange = new EventEmitter<boolean>();
  @Output() readonly valueChange = new EventEmitter<string | boolean>();

  value = '';
  checked = false;
  selected = '';
  previewControl = new FormControl<string | boolean>('', { nonNullable: true });

  ngOnInit(): void {
    this.previewControl.statusChanges.subscribe(() => this.emitValidity());
    this.previewControl.valueChanges.subscribe(value => { this.emitValidity(); this.valueChange.emit(value); });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['field']) {
      this.previewControl = new FormControl<string | boolean>(this.initialValue ?? '', { nonNullable: true, validators: buildFieldValidators(this.field?.validation_rules ?? {}) });
      this.previewControl.statusChanges.subscribe(() => this.emitValidity());
      this.previewControl.valueChanges.subscribe(value => { this.emitValidity(); this.valueChange.emit(value); });
      this.emitValidity();
    } else if (changes['initialValue']) {
      this.previewControl.setValue(this.initialValue ?? '', { emitEvent: false });
    }
  }

  private emitValidity(): void {
    this.validityChange.emit(this.previewControl.valid);
  }

  get isValid(): boolean { return this.previewControl.valid && this.previewControl.touched; }

  get controlKind() {
    return resolveControlKind(this.field?.field_type);
  }

  get validationMessage(): string {
    return getValidationMessage(this.previewControl, this.field?.validation_messages ?? {});
  }

  get validationMessages(): string[] {
    return getConfiguredValidationMessages(
      this.field?.validation_rules ?? {},
      this.field?.validation_messages ?? {},
      this.field?.label ?? 'This field',
    );
  }

  get options(): string[] {
    const options = (this.field as FieldTemplate & { options?: unknown[] })?.options;
    return Array.isArray(options) ? options.map(String) : ['Option one', 'Option two', 'Option three'];
  }

  get inputType(): string {
    return this.field?.validation_rules?.['email'] ? 'email' : 'text';
  }

  get required(): boolean {
    return Boolean(this.field?.validation_rules?.['required']);
  }

  get maxLength(): number | null {
    const value = this.field?.validation_rules?.['maxlength'];
    return typeof value === 'number' ? value : null;
  }
}
