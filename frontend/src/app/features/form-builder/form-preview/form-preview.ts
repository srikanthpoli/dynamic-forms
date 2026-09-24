import { ChangeDetectionStrategy, Component, EventEmitter, HostListener, Input, Output } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { CdkDragDrop, CdkDrag, CdkDropList, moveItemInArray } from '@angular/cdk/drag-drop';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { FormDefinitionJson, FormLayoutNode, FormVersion } from '../../../core/models/form.models';
import { FieldLivePreviewComponent } from '../../field-builder/field-live-preview/field-live-preview';
import { FormCodePreviewComponent } from '../form-code-preview/form-code-preview';

@Component({
  selector: 'app-form-preview',
  standalone: true,
  imports: [JsonPipe, CdkDrag, CdkDropList, MatButtonModule, MatButtonToggleModule, MatCheckboxModule, FieldLivePreviewComponent, FormCodePreviewComponent],
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
  @Output() readonly layoutChanged = new EventEmitter<FormDefinitionJson>();

  activeAction: 'save' | 'publish' | 'new-version' = 'save';
  layoutEditMode = false;
  private resizingFieldId: string | null = null;

  private readonly fieldValidity = new Map<string, boolean>();

  get sortedLayout() {
    return [...(this.form?.layout_tree ?? [])].sort((a, b) => a.order - b.order);
  }

  fieldKey(node: FormDefinitionJson['layout_tree'][number], index: number): string {
    return node.field?.id ?? node.field_id ?? `field-${index}`;
  }

  onFieldValidityChange(fieldId: string, valid: boolean): void {
    this.fieldValidity.set(fieldId, valid);
  }

  get isFormValid(): boolean {
    const layout = this.sortedLayout;
    if (!layout.length) return false;
    return layout.every((node, index) => this.fieldValidity.get(this.fieldKey(node, index)) === true);
  }

  get canEditLayout(): boolean {
    return this.layoutEditMode && (!this.selectedVersion || this.selectedVersion.status === 'draft');
  }

  setLayoutMode(mode: 'edit' | 'preview'): void {
    this.layoutEditMode = mode === 'edit';
    if (!this.layoutEditMode) this.resizingFieldId = null;
  }

  setLayoutEditMode(enabled: boolean): void {
    this.layoutEditMode = enabled;
    if (!enabled) this.resizingFieldId = null;
  }

  onDrop(event: CdkDragDrop<FormLayoutNode[]>): void {
    if (!this.form || !this.canEditLayout || event.previousIndex === event.currentIndex) return;

    const layout = this.sortedLayout;
    moveItemInArray(layout, event.previousIndex, event.currentIndex);
    const nextLayout = layout.map((node, order) => ({ ...node, order }));
    this.emitLayout(nextLayout);
  }

  setColumnSpan(fieldId: string, columnSpan: number): void {
    if (!this.form || !this.canEditLayout) return;
    const nextLayout = this.sortedLayout.map((node, order) => ({
      ...node,
      order,
      column_span: this.fieldKey(node, order) === fieldId ? columnSpan : (node.column_span || 12),
    }));
    this.emitLayout(nextLayout);
  }

  startResize(event: PointerEvent, fieldId: string): void {
    if (!this.canEditLayout) return;
    event.preventDefault();
    event.stopPropagation();
    this.resizingFieldId = fieldId;
  }

  @HostListener('document:pointermove', ['$event'])
  resizeField(event: PointerEvent): void {
    if (!this.resizingFieldId || !this.form) return;
    const target = event.target as HTMLElement;
    const grid = target.closest('.fields-preview') ?? document.querySelector('.fields-preview');
    if (!grid) return;

    const bounds = grid.getBoundingClientRect();
    const gap = Number.parseFloat(getComputedStyle(grid).columnGap) || 0;
    const columnWidth = (bounds.width - gap * 11) / 12;
    const span = Math.max(1, Math.min(12, Math.round((event.clientX - bounds.left + gap) / (columnWidth + gap))));
    this.setColumnSpan(this.resizingFieldId, span);
  }

  @HostListener('document:pointerup')
  stopResize(): void {
    this.resizingFieldId = null;
  }

  private emitLayout(layout: FormDefinitionJson['layout_tree']): void {
    this.layoutChanged.emit({ ...this.form!, layout_tree: layout });
  }

  selectAction(action: 'save' | 'publish' | 'new-version'): void {
    this.activeAction = action;
    if (action === 'save') this.saveRequested.emit();
    if (action === 'publish') this.publishRequested.emit();
    if (action === 'new-version') this.newVersionRequested.emit();
  }
}
