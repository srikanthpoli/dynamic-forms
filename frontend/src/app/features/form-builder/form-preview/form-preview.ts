import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { FormDefinitionJson, FormVersion } from '../../../core/models/form.models';
import { FieldLivePreviewComponent } from '../../field-builder/field-live-preview/field-live-preview';
import { FormCodePreviewComponent } from '../form-code-preview/form-code-preview';

@Component({
  selector: 'app-form-preview',
  standalone: true,
  imports: [JsonPipe, MatButtonModule, MatButtonToggleModule, FieldLivePreviewComponent, FormCodePreviewComponent],
  templateUrl: './form-preview.html',
  styleUrl: './form-preview.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FormPreviewComponent {
  @Input() form: FormDefinitionJson | null = null;
  @Input() isLoading = false;
  @Input() isSaving = false;
  @Input() error = '';
  @Input() hasGenerated = false;
  @Input() isEditing = false;
  @Input() versionBump: 'major' | 'minor' | 'patch' = 'patch';
  @Input() selectedVersion: FormVersion | null = null;
  @Input() isPublishing = false;
  @Output() readonly saveRequested = new EventEmitter<void>();
  @Output() readonly formSubmitted = new EventEmitter<void>();
  @Output() readonly versionBumpChange = new EventEmitter<'major' | 'minor' | 'patch'>();
  @Output() readonly publishRequested = new EventEmitter<void>();
  @Output() readonly newVersionRequested = new EventEmitter<void>();

  activeAction: 'save' | 'publish' | 'new-version' = 'save';

  private readonly fieldValidity = new Map<string, boolean>();

  get sortedLayout() {
    return [...(this.form?.layout_tree ?? [])].sort((a, b) => a.order - b.order);
  }

  onFieldValidityChange(fieldId: string, valid: boolean): void {
    this.fieldValidity.set(fieldId, valid);
  }

  get isFormValid(): boolean {
    const layout = this.sortedLayout;
    if (!layout.length) return false;
    return layout.every(node => this.fieldValidity.get(node.field_id) === true);
  }

  selectAction(action: 'save' | 'publish' | 'new-version'): void {
    this.activeAction = action;
    if (action === 'save') this.saveRequested.emit();
    if (action === 'publish') this.publishRequested.emit();
    if (action === 'new-version') this.newVersionRequested.emit();
  }
}
