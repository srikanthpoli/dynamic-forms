import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { finalize, timeout } from 'rxjs';
import { FormBuilderApiService } from '../../../core/services/form-builder-api.service';
import { FieldBuilderApiService } from '../../../core/services/field-builder-api.service';
import { FormDefinition, FormDefinitionJson, FormVersion } from '../../../core/models/form.models';
import { FieldTemplate } from '../../../core/models/field.models';
import { FormPromptPanelComponent } from '../form-prompt-panel/form-prompt-panel';
import { FormPreviewComponent } from '../form-preview/form-preview';
import { FormLibraryComponent } from '../form-library/form-library';
import { FieldLibraryComponent } from '../../field-builder/field-library/field-library';
import { createSessionId } from '../../../core/utils/session-id';

@Component({
  selector: 'app-form-builder-page',
  standalone: true,
  imports: [FormPromptPanelComponent, FormPreviewComponent, FormLibraryComponent, FieldLibraryComponent],
  templateUrl: './form-builder-page.html',
  styleUrl: './form-builder-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FormBuilderPageComponent implements OnInit {
  private readonly api = inject(FormBuilderApiService);
  private readonly fieldApi = inject(FieldBuilderApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly router = inject(Router);

  sessionId = createSessionId('form');
  forms: FormDefinition[] = [];
  fields: FieldTemplate[] = [];
  messages: { role: 'user' | 'agent'; text: string }[] = [];
  draft: FormDefinitionJson | null = null;
  isLoading = false;
  isSaving = false;
  isEditing = false;
  error = '';

  currentFormId: string | null = null;
  currentForm: FormDefinition | null = null;
  versions: FormVersion[] = [];
  selectedVersion: FormVersion | null = null;
  publishingVersionId: string | null = null;
  versionBump: 'major' | 'minor' | 'patch' = 'patch';
  versionPendingDeletion: FormVersion | null = null;
  isDeletingVersion = false;

  get showBuilderAgent(): boolean {
    return !this.currentFormId || this.selectedVersion?.status === 'draft';
  }

  ngOnInit(): void {
    this.loadLibrary();
    this.loadFields();
  }

  selectForm(form: FormDefinition): void {
    this.sessionId = createSessionId('form-edit');
    this.draft = null;
    this.isEditing = true;
    this.error = '';
    this.currentFormId = form.id;
    this.currentForm = form;
    this.selectedVersion = null;
    this.messages = [{ role: 'agent', text: `Loaded "${form.title}" as the working context. Describe the changes you want, then save a new version.` }];
    this.loadVersions();
    this.changeDetector.markForCheck();
  }

  startNewSession(): void {
    this.sessionId = createSessionId('form');
    this.draft = null;
    this.messages = [];
    this.isEditing = false;
    this.error = '';
    this.currentFormId = null;
    this.currentForm = null;
    this.versions = [];
    this.selectedVersion = null;
    this.changeDetector.markForCheck();
  }

  noop(): void {
    // Field library is shown for reference only on this page.
  }

  editField(field: FieldTemplate): void {
    if (field.id) this.router.navigate(['/'], { queryParams: { fieldId: field.id } });
  }

  setVersionBump(bump: 'major' | 'minor' | 'patch'): void {
    this.versionBump = bump;
  }

  createNewVersion(): void {
    this.selectedVersion = null;
    this.error = '';
    if (!this.draft) return;

    if (this.currentFormId) {
      this.isSaving = true;
      this.saveDraftVersion(this.currentFormId, true);
      return;
    }

    this.save();
  }

  generate(prompt: string): void {
    this.messages = [...this.messages, { role: 'user', text: prompt }];
    this.isLoading = true;
    this.error = '';
    this.api.buildForm(this.sessionId, prompt, this.draft).pipe(
      timeout(120000),
      finalize(() => {
        this.isLoading = false;
        this.changeDetector.markForCheck();
      }),
    ).subscribe({
      next: response => {
        this.draft = response.form_definition;
        this.messages = [...this.messages, {
          role: 'agent',
          text: response.assistant_message
            ?? `Assembled "${response.form_definition.title}" with ${response.form_definition.layout_tree.length} field(s). Review the preview below, or tell me what to change.`,
        }];
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.name === 'TimeoutError'
          ? 'The Form Builder took too long to respond. Check the backend logs and try again.'
          : 'The Form Builder could not reach the backend. Check that FastAPI is running on port 8000.';
        this.changeDetector.markForCheck();
      },
    });
  }

  save(): void {
    if (!this.draft) return;
    this.isSaving = true;
    this.error = '';

    if (this.currentFormId) {
      if (this.selectedVersion?.status === 'draft') {
        this.updateSelectedDraft(this.currentFormId, this.selectedVersion);
      } else {
        this.saveDraftVersion(this.currentFormId);
      }
      return;
    }

    this.api.createFormDefinition(this.draft.title, this.draft.description ?? null).pipe(
      timeout(30000),
    ).subscribe({
      next: definition => {
        this.currentFormId = definition.id;
        this.currentForm = definition;
        this.saveDraftVersion(definition.id);
      },
      error: (err: HttpErrorResponse) => {
        this.isSaving = false;
        this.error = err.status === 409
          ? (err.error?.detail ?? 'A form with this name already exists.')
          : 'This form could not be saved. Please try again.';
        this.changeDetector.markForCheck();
      },
    });
  }

  publishVersion(version: FormVersion): void {
    if (!this.currentFormId) return;
    this.publishingVersionId = version.id;
    this.changeDetector.markForCheck();
    this.api.publishVersion(this.currentFormId, version.id).pipe(
      timeout(30000),
      finalize(() => {
        this.publishingVersionId = null;
        this.changeDetector.markForCheck();
      }),
    ).subscribe({
      next: () => {
        this.loadVersions();
        this.loadLibrary();
      },
      error: () => {
        this.error = 'This version could not be published.';
        this.changeDetector.markForCheck();
      },
    });
  }

  publishSelectedVersion(): void {
    if (this.selectedVersion?.status === 'draft') {
      this.publishVersion(this.selectedVersion);
    }
  }

  requestDeleteVersion(version: FormVersion): void {
    this.versionPendingDeletion = version;
  }

  cancelDeleteVersion(): void {
    if (!this.isDeletingVersion) this.versionPendingDeletion = null;
  }

  confirmDeleteVersion(): void {
    if (!this.currentFormId || !this.versionPendingDeletion) return;
    const version = this.versionPendingDeletion;
    this.isDeletingVersion = true;
    this.api.deleteVersion(this.currentFormId, version.id).pipe(
      timeout(30000),
      finalize(() => {
        this.isDeletingVersion = false;
        this.changeDetector.markForCheck();
      }),
    ).subscribe({
      next: () => {
        this.versionPendingDeletion = null;
        if (this.selectedVersion?.id === version.id) this.selectedVersion = null;
        this.loadVersions();
      },
      error: (err: HttpErrorResponse) => {
        this.error = err.error?.detail ?? 'This version could not be deleted.';
        this.versionPendingDeletion = null;
        this.changeDetector.markForCheck();
      },
    });
  }

  selectVersion(version: FormVersion): void {
    this.selectedVersion = version;
    this.draft = {
      title: this.currentForm?.title ?? 'Untitled form',
      description: this.currentForm?.description,
      layout_tree: this.hydrateLayout(version.layout_tree),
    };
    this.error = '';
    this.changeDetector.markForCheck();
  }

  private saveDraftVersion(formId: string, selectCreatedVersion = false): void {
    this.api.saveVersionFromDefinition(formId, this.versionBump, this.draft!).pipe(
      timeout(30000),
      finalize(() => {
        this.isSaving = false;
        this.changeDetector.markForCheck();
      }),
    ).subscribe({
      next: response => {
        this.loadVersions(selectCreatedVersion ? response.version_id : undefined);
        this.loadLibrary();
      },
      error: (err: HttpErrorResponse) => {
        this.error = err.status === 409
          ? (err.error?.detail ?? 'This form version already exists.')
          : 'This form version could not be saved.';
        this.changeDetector.markForCheck();
      },
    });
  }

  private updateSelectedDraft(formId: string, version: FormVersion): void {
    this.api.updateDraftVersion(formId, version.version_number, this.draft!).pipe(
      timeout(30000),
      finalize(() => {
        this.isSaving = false;
        this.changeDetector.markForCheck();
      }),
    ).subscribe({
      next: () => this.loadVersions(),
      error: (err: HttpErrorResponse) => {
        this.error = err.error?.detail ?? 'This draft could not be updated.';
        this.changeDetector.markForCheck();
      },
    });
  }

  private loadVersions(versionIdToSelect?: string): void {
    if (!this.currentFormId) return;
    this.api.listFormVersions(this.currentFormId).subscribe({
      next: versions => {
        this.versions = versions;
        const selected = versions.find(version => version.id === versionIdToSelect)
          ?? versions.find(version => version.id === this.selectedVersion?.id)
          ?? versions[0];
        if (selected) {
          this.selectVersion(selected);
        }
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.versions = [];
        this.changeDetector.markForCheck();
      },
    });
  }

  private loadLibrary(): void {
    this.api.listFormDefinitions().subscribe({
      next: forms => {
        this.forms = forms;
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.forms = [];
        this.changeDetector.markForCheck();
      },
    });
  }

  private loadFields(): void {
    this.fieldApi.listFields().subscribe({
      next: fields => {
        this.fields = fields;
        if (this.selectedVersion) {
          this.selectVersion(this.selectedVersion);
        }
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.fields = [];
        this.changeDetector.markForCheck();
      },
    });
  }

  private hydrateLayout(layoutTree: FormVersion['layout_tree']): FormDefinitionJson['layout_tree'] {
    return layoutTree.map(node => ({
      ...node,
      field: node.field ?? this.fields.find(field => field.id === node.field_id) ?? null,
    }));
  }
}
