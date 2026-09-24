import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FieldTemplate } from '../../../core/models/field.models';

@Component({
  selector: 'app-field-library',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './field-library.html',
  styleUrl: './field-library.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldLibraryComponent {
  @Input() fields: FieldTemplate[] = [];
  @Output() readonly fieldSelected = new EventEmitter<FieldTemplate>();
  @Output() readonly fieldDeleted = new EventEmitter<FieldTemplate>();
}
