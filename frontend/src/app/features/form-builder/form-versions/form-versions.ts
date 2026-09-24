import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormVersion } from '../../../core/models/form.models';

@Component({
  selector: 'app-form-versions',
  standalone: true,
  templateUrl: './form-versions.html',
  styleUrl: './form-versions.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FormVersionsComponent {
  @Input() versions: FormVersion[] = [];
  @Input() selectedVersionId: string | null = null;
  @Input() publishingVersionId: string | null = null;
  @Output() readonly versionSelected = new EventEmitter<FormVersion>();
  @Output() readonly publishRequested = new EventEmitter<FormVersion>();
}
