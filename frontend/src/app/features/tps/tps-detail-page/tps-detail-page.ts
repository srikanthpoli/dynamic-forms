import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Location } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { IrForm, TpsApiService, TpsIr } from '../../../core/services/tps-api.service';
import { TpsIrAssistComponent } from '../tps-ir-assist/tps-ir-assist';
import { FieldLivePreviewComponent } from '../../field-builder/field-live-preview/field-live-preview';
import { FieldTemplate } from '../../../core/models/field.models';

@Component({
  selector: 'app-tps-detail-page',
  standalone: true,
  imports: [DatePipe, FormsModule, TpsIrAssistComponent, FieldLivePreviewComponent],
  templateUrl: './tps-detail-page.html',
  styleUrl: './tps-detail-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TpsDetailPageComponent implements OnInit {
  private readonly clientMessageKey = 'client_message';
  private readonly api = inject(TpsApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly location = inject(Location);
  private readonly changeDetector = inject(ChangeDetectorRef);

  ir: TpsIr | null = null;
  isLoading = true;
  isSaving = false;
  error = '';
  success = '';
  irForms: IrForm[] = [];
  releasingFormId: string | null = null;
  deletingFormId: string | null = null;
  pendingDeleteForm: IrForm | null = null;
  savingSubmissionId: string | null = null;
  recallingFormId: string | null = null;
  activeTab: 'detail' | 'forms' = 'detail';

  selectTab(tab: 'detail' | 'forms'): void {
    this.activeTab = tab;
    if (tab === 'forms' && this.ir) {
      this.loadIrForms(this.ir.ir_number);
    }
  }

  ngOnInit(): void {
    const irNumber = this.route.snapshot.paramMap.get('irNumber');
    if (!irNumber) {
      this.error = 'Implementation request not found.';
      this.isLoading = false;
      this.changeDetector.markForCheck();
      return;
    }
    this.api.getIr(irNumber).subscribe({
      next: ir => {
        this.ir = ir;
        this.loadIrForms(ir.ir_number);
        this.isLoading = false;
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The implementation request could not be loaded.';
        this.isLoading = false;
        this.changeDetector.markForCheck();
      },
    });
  }

  loadIrForms(irNumber: string): void {
    this.api.listIrForms(irNumber).subscribe({
      next: forms => { this.irForms = forms; this.changeDetector.markForCheck(); },
      error: error => {
        this.error = error?.error?.detail ?? 'Assigned forms could not be loaded.';
        this.changeDetector.markForCheck();
      },
    });
  }

  onFormAssigned(): void {
    if (this.ir) {
      this.activeTab = 'forms';
      this.loadIrForms(this.ir.ir_number);
    }
  }

  releaseForm(form: IrForm): void {
    if (!this.ir || this.releasingFormId || form.status === 'released') return;
    this.releasingFormId = form.id;
    this.api.releaseIrForm(this.ir.ir_number, form.id).subscribe({
      next: () => {
        this.success = 'Form released and initial submission created.';
        this.releasingFormId = null;
        this.loadIrForms(this.ir!.ir_number);
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The form could not be released.';
        this.releasingFormId = null;
        this.changeDetector.markForCheck();
      },
    });
  }

  recallForm(form: IrForm): void {
    if (!this.ir || this.recallingFormId || form.status !== 'released') return;
    this.recallingFormId = form.id;
    this.api.recallIrForm(this.ir.ir_number, form.id).subscribe({
      next: () => {
        this.success = 'Form recalled and returned to draft.';
        this.recallingFormId = null;
        this.loadIrForms(this.ir!.ir_number);
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The form could not be recalled.';
        this.recallingFormId = null;
        this.changeDetector.markForCheck();
      },
    });
  }

  requestDelete(form: IrForm): void {
    if (this.deletingFormId || form.status !== 'assigned') return;
    this.pendingDeleteForm = form;
    this.changeDetector.markForCheck();
  }

  deleteForm(): void {
    const form = this.pendingDeleteForm;
    if (!this.ir || !form || this.deletingFormId || form.status !== 'assigned') return;
    this.pendingDeleteForm = null;
    this.deletingFormId = form.id;
    this.api.deleteIrForm(this.ir.ir_number, form.id).subscribe({
      next: () => {
        this.success = 'Form Review deleted.';
        this.deletingFormId = null;
        this.loadIrForms(this.ir!.ir_number);
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The Form Review could not be deleted.';
        this.deletingFormId = null;
        this.changeDetector.markForCheck();
      },
    });
  }

  cancelDelete(): void {
    this.pendingDeleteForm = null;
  }

  saveSubmission(form: IrForm): void {
    if (!this.ir || this.savingSubmissionId) return;
    this.savingSubmissionId = form.id;
    this.api.saveIrFormSubmission(this.ir.ir_number, form.id, form.submission_data ?? {}).subscribe({
      next: savedForm => {
        Object.assign(form, savedForm);
        this.success = 'Form Review saved.';
        this.savingSubmissionId = null;
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The Form Review could not be saved.';
        this.savingSubmissionId = null;
        this.changeDetector.markForCheck();
      },
    });
  }

  fieldValue(form: IrForm, field: FieldTemplate): string | boolean | null {
    const value = form.submission_data?.[field.name];
    return typeof value === 'string' || typeof value === 'boolean' ? value : null;
  }

  captureFieldValue(form: IrForm, field: FieldTemplate, value: string | boolean): void {
    form.submission_data = { ...(form.submission_data ?? {}), [field.name]: value };
  }

  clientMessage(form: IrForm): string {
    const value = form.submission_data?.[this.clientMessageKey];
    return typeof value === 'string' ? value : '';
  }

  captureClientMessage(form: IrForm, value: string): void {
    form.submission_data = { ...(form.submission_data ?? {}), [this.clientMessageKey]: value };
  }

  eventLabel(eventType: string): string {
    return ({ assigned: 'Assigned', saved: 'Form Review saved', released: 'Released to client', recalled: 'Recalled to draft', submitted: 'Submitted back' } as Record<string, string>)[eventType] ?? eventType;
  }

  goBack(): void {
    this.location.back();
  }

  save(): void {
    if (!this.ir || this.isSaving) return;
    this.isSaving = true;
    this.error = '';
    this.success = '';
    this.api.updateIr(this.ir.ir_number, this.ir).subscribe({
      next: ir => {
        this.ir = ir;
        this.isSaving = false;
        this.success = 'Implementation request updated successfully.';
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.isSaving = false;
        this.error = error?.error?.detail ?? 'The implementation request could not be updated.';
        this.changeDetector.markForCheck();
      },
    });
  }
}
