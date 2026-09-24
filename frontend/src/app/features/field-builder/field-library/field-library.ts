import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { DecimalPipe, JsonPipe } from '@angular/common';
import { FieldTemplate } from '../../../core/models/field.models';

@Component({
  selector: 'app-field-library',
  standalone: true,
  imports: [DecimalPipe, JsonPipe],
  templateUrl: './field-library.html',
  styleUrl: './field-library.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldLibraryComponent {
  @Input() fields: FieldTemplate[] = [];
  @Input() readOnly = false;
  @Output() readonly fieldSelected = new EventEmitter<FieldTemplate>();
  @Output() readonly fieldDeleted = new EventEmitter<FieldTemplate>();
  @Output() readonly fieldEditRequested = new EventEmitter<FieldTemplate>();
}
