import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { FieldTemplate } from '../../../core/models/field.models';
import { FieldLivePreviewComponent } from '../field-live-preview/field-live-preview';
import { FieldCodePreviewComponent } from '../field-code-preview/field-code-preview';

@Component({
  selector: 'app-field-preview',
  standalone: true,
  imports: [FieldCodePreviewComponent, FieldLivePreviewComponent, JsonPipe, MatButtonModule],
  templateUrl: './field-preview.html',
  styleUrl: './field-preview.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldPreviewComponent {
  @Input() field: FieldTemplate | null = null;
  @Input() isLoading = false;
  @Input() isSaving = false;
  @Input() error = '';
  @Input() hasGenerated = false;
  @Input() isEditing = false;
  @Output() readonly publishRequested = new EventEmitter<void>();
}
