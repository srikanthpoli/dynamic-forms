import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { finalize, timeout } from 'rxjs';
import { FieldBuilderApiService } from '../../../core/services/field-builder-api.service';
import { FieldTemplate } from '../../../core/models/field.models';
import { FieldPromptPanelComponent } from '../field-prompt-panel/field-prompt-panel';
import { FieldPreviewComponent } from '../field-preview/field-preview';
import { FieldLibraryComponent } from '../field-library/field-library';
import { createSessionId } from '../../../core/utils/session-id';

@Component({
  selector: 'app-field-builder-page',
  standalone: true,
  imports: [FieldPromptPanelComponent, FieldPreviewComponent, FieldLibraryComponent],
  templateUrl: './field-builder-page.html',
  styleUrl: './field-builder-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldBuilderPageComponent implements OnInit {
  private readonly api = inject(FieldBuilderApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly route = inject(ActivatedRoute);
  sessionId = createSessionId('field');
  fields: FieldTemplate[] = [];
  messages: { role: 'user' | 'agent'; text: string }[] = [];
  draft: FieldTemplate | null = null;
  isLoading = false;
  isSaving = false;
  isEditing = false;
  error = '';
  fieldPendingDeletion: FieldTemplate | null = null;
  isDeleting = false;
  private requestedFieldId: string | null = null;

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(params => {
      this.requestedFieldId = params.get('fieldId');
      this.selectRequestedField();
    });
    this.loadLibrary();
  }

  selectField(field: FieldTemplate): void {
    this.sessionId = createSessionId('field-edit');
    this.draft = { ...field };
    this.isEditing = true;
    this.error = '';
    this.messages = [{ role: 'agent', text: `Loaded “${field.label}” as the working context. Describe the changes you want, then republish the updated field.` }];
    this.changeDetector.markForCheck();
  }

  startNewSession(): void {
    this.sessionId = createSessionId('field');
    this.draft = null;
    this.messages = [];
    this.isEditing = false;
    this.error = '';
    this.changeDetector.markForCheck();
  }

  deleteField(field: FieldTemplate): void {
    if (!field.id) return;
    this.fieldPendingDeletion = field;
    this.changeDetector.markForCheck();
  }

  cancelDelete(): void {
    if (this.isDeleting) return;
    this.fieldPendingDeletion = null;
    this.changeDetector.markForCheck();
  }

  confirmDelete(): void {
    const field = this.fieldPendingDeletion;
    if (!field?.id || this.isDeleting) return;
    this.isDeleting = true;
    this.api.deleteField(field.id).subscribe({
      next: () => {
        this.fields = this.fields.filter(item => item.id !== field.id);
        if (this.draft?.id === field.id) this.startNewSession();
        this.fieldPendingDeletion = null;
        this.isDeleting = false;
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.error = 'This field could not be deleted.';
        this.isDeleting = false;
        this.changeDetector.markForCheck();
      },
    });
  }

  generate(prompt: string): void {
    this.messages = [...this.messages, { role: 'user', text: prompt }];
    this.isLoading = true;
    this.error = '';
    this.api.generateFieldStream(this.sessionId, prompt, this.draft).pipe(
      timeout(120000),
      finalize(() => {
        this.isLoading = false;
        this.changeDetector.markForCheck();
      }),
    ).subscribe({
      next: event => {
        if (event.type === 'status') {
          this.messages = [...this.messages, { role: 'agent', text: (event.data as { message: string }).message }];
        } else if (event.type === 'complete') {
          const field = event.data as FieldTemplate;
          this.draft = this.isEditing && this.draft?.id
            ? { ...field, id: this.draft.id }
            : field;
          this.messages = [...this.messages, { role: 'agent', text: field.assistant_message || JSON.stringify(field, null, 2) }];
        } else if (event.type === 'error') {
          this.error = (event.data as { message: string }).message;
        }
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.name === 'TimeoutError'
          ? 'The Field Builder took too long to respond. Check the backend logs and try again.'
          : error?.error?.detail
            ?? 'The Field Builder could not reach the backend. Check that FastAPI is running on port 8000.';
        this.changeDetector.markForCheck();
      },
    });
  }

  publish(): void {
    if (!this.draft) return;
    this.isSaving = true;
    this.error = '';
    this.saveField(this.draft).pipe(
      timeout(30000),
      finalize(() => {
        this.isSaving = false;
        this.changeDetector.markForCheck();
      }),
    ).subscribe({
      next: field => {
        this.draft = field;
        this.loadLibrary();
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.error = 'This field could not be published. Its name may already exist.';
        this.changeDetector.markForCheck();
      },
    });
  }

  private saveField(field: FieldTemplate) {
    return this.isEditing && field.id
      ? this.api.overrideField(field.id, field)
      : this.api.publishField(field);
  }

  private loadLibrary(): void {
    this.api.listFields().subscribe({
      next: fields => {
        this.fields = fields;
        this.selectRequestedField();
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.fields = [];
        this.changeDetector.markForCheck();
      },
    });
  }

  private selectRequestedField(): void {
    if (!this.requestedFieldId) return;
    const field = this.fields.find(item => item.id === this.requestedFieldId);
    if (field) {
      this.selectField(field);
      this.requestedFieldId = null;
    }
  }
}
