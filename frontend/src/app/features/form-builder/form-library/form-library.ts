import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormDefinition, FormVersion } from '../../../core/models/form.models';

@Component({
  selector: 'app-form-library',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './form-library.html',
  styleUrl: './form-library.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FormLibraryComponent {
  @Input() forms: FormDefinition[] = [];
  @Input() versions: FormVersion[] = [];
  @Input() selectedFormId: string | null = null;
  @Input() selectedVersionId: string | null = null;
  @Output() readonly formSelected = new EventEmitter<FormDefinition>();
  @Output() readonly versionSelected = new EventEmitter<FormVersion>();
  @Output() readonly versionDeleted = new EventEmitter<FormVersion>();

  historyExpanded = true;

  toggleHistory(): void {
    this.historyExpanded = !this.historyExpanded;
  }

  selectForm(form: FormDefinition): void {
    this.historyExpanded = true;
    this.formSelected.emit(form);
  }
}
