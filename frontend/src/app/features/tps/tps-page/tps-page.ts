import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { forkJoin, map } from 'rxjs';
import { IrForm, TpsApiService, TpsIr } from '../../../core/services/tps-api.service';
import { FieldLivePreviewComponent } from '../../field-builder/field-live-preview/field-live-preview';
import { FieldTemplate } from '../../../core/models/field.models';

interface ReleasedFormRow {
  irNumber: string;
  customerName: string;
  form: IrForm;
}

@Component({
  selector: 'app-tps-page',
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule, FieldLivePreviewComponent],
  templateUrl: './tps-page.html',
  styleUrl: './tps-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TpsPageComponent implements OnInit {
  private readonly api = inject(TpsApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  irs: TpsIr[] = [];
  releasedForms: ReleasedFormRow[] = [];
  isLoading = true;
  isLoadingReleased = false;
  error = '';
  success = '';
  activeTab: 'irs' | 'released' = 'irs';
  savingSubmissionId: string | null = null;
  submittingFormId: string | null = null;
  private readonly clientMessageKey = 'client_message';

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(params => {
      this.activeTab = params.get('tab') === 'released' ? 'released' : 'irs';
      if (this.activeTab === 'released' && this.irs.length) this.loadReleasedForms();
      this.changeDetector.markForCheck();
    });
    this.api.listIrs().subscribe({
      next: irs => {
        this.irs = irs;
        this.isLoading = false;
        this.loadReleasedForms();
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The TPS implementation requests could not be loaded.';
        this.isLoading = false;
        this.changeDetector.markForCheck();
      },
    });
  }

  selectTab(tab: 'irs' | 'released'): void {
    this.activeTab = tab;
    if (tab === 'released') this.loadReleasedForms();
  }

  private loadReleasedForms(): void {
    if (!this.irs.length) {
      this.releasedForms = [];
      return;
    }
    this.isLoadingReleased = true;
    forkJoin(this.irs.map(ir => this.api.listIrForms(ir.ir_number).pipe(
      map(forms => forms
        .filter(form => form.status === 'released')
        .map(form => ({ irNumber: ir.ir_number, customerName: ir.customer_name, form }))),
    ))).subscribe({
      next: groups => {
        this.releasedForms = groups.flat();
        this.isLoadingReleased = false;
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.error?.detail ?? 'Released Form Reviews could not be loaded.';
        this.isLoadingReleased = false;
        this.changeDetector.markForCheck();
      },
    });
  }

  openIr(ir: TpsIr): void {
    this.router.navigate(['/tps/irs', ir.ir_number]);
  }

  saveSubmission(row: ReleasedFormRow): void {
    if (this.savingSubmissionId) return;
    this.savingSubmissionId = row.form.id;
    this.api.saveIrFormSubmission(row.irNumber, row.form.id, row.form.submission_data ?? {}).subscribe({
      next: savedForm => {
        row.form = savedForm;
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

  submitSubmission(row: ReleasedFormRow): void {
    if (this.submittingFormId || row.form.status !== 'released') return;
    this.submittingFormId = row.form.id;
    this.api.submitIrForm(row.irNumber, row.form.id).subscribe({
      next: () => {
        this.success = 'Form Review submitted back successfully.';
        this.submittingFormId = null;
        this.loadReleasedForms();
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The Form Review could not be submitted back.';
        this.submittingFormId = null;
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
}
