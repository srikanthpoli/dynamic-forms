import { ChangeDetectionStrategy, ChangeDetectorRef, Component, HostListener, OnDestroy, OnInit, inject } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { forkJoin, map } from 'rxjs';
import { IrForm, TpsApiService, TpsIr } from '../../../core/services/tps-api.service';
import { FieldLivePreviewComponent } from '../../field-builder/field-live-preview/field-live-preview';
import { FieldTemplate } from '../../../core/models/field.models';
import { TpsIrAssistComponent } from '../tps-ir-assist/tps-ir-assist';

interface ReleasedFormRow {
  irNumber: string;
  customerName: string;
  form: IrForm;
}

@Component({
  selector: 'app-tps-page',
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule, FieldLivePreviewComponent, TpsIrAssistComponent],
  templateUrl: './tps-page.html',
  styleUrl: './tps-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TpsPageComponent implements OnInit, OnDestroy {
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
  activeAssistFormId: string | null = null;
  activeAssistIr: TpsIr | null = null;
  activeAssistContextKey = '';
  isAssistMinimized = false;
  isAssistDragging = false;
  assistPosition: { left: number; top: number } | null = null;
  private assistDragOffset = { x: 0, y: 0 };
  private assistDragSize = { width: 0, height: 0 };
  private readonly clientMessageKey = 'client_message';
  private readonly assistPointerMove = (event: PointerEvent) => this.dragAssist(event);
  private readonly assistPointerUp = () => this.stopAssistDrag();

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(params => {
      this.activeTab = params.get('tab') === 'released' ? 'released' : 'irs';
      if (this.activeTab === 'released' && this.irs.length) this.loadReleasedForms();
      if (this.activeTab !== 'released') this.closeIrAssist();
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
    if (tab !== 'released') this.closeIrAssist();
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

  openIrAssist(row: ReleasedFormRow): void {
    const ir = this.irs.find(item => item.ir_number === row.irNumber) ?? null;
    if (!ir) {
      this.error = 'The IR context for this released form could not be loaded.';
      this.changeDetector.markForCheck();
      return;
    }
    this.activeAssistFormId = row.form.id;
    this.activeAssistIr = ir;
    this.activeAssistContextKey = `${row.form.id}-${Date.now()}`;
    this.isAssistMinimized = false;
    this.assistPosition = null;
    this.changeDetector.markForCheck();
  }

  toggleAssistMinimized(): void {
    this.isAssistMinimized = !this.isAssistMinimized;
    this.changeDetector.markForCheck();
  }

  closeIrAssist(): void {
    this.activeAssistFormId = null;
    this.activeAssistIr = null;
    this.activeAssistContextKey = '';
    this.isAssistMinimized = false;
    this.assistPosition = null;
    this.stopAssistDrag();
    this.changeDetector.markForCheck();
  }

  @HostListener('window:blur')
  closeAssistOnWindowBlur(): void {
    this.closeIrAssist();
  }

  @HostListener('document:visibilitychange')
  closeAssistOnVisibilityChange(): void {
    if (document.hidden) this.closeIrAssist();
  }

  startAssistDrag(event: PointerEvent): void {
    const panel = (event.currentTarget as HTMLElement).closest('.floating-assist') as HTMLElement | null;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    this.assistPosition = { left: rect.left, top: rect.top };
    this.assistDragOffset = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    this.assistDragSize = { width: rect.width, height: rect.height };
    this.isAssistDragging = true;
    document.addEventListener('pointermove', this.assistPointerMove);
    document.addEventListener('pointerup', this.assistPointerUp, { once: true });
    event.preventDefault();
    this.changeDetector.markForCheck();
  }

  private dragAssist(event: PointerEvent): void {
    if (!this.isAssistDragging) return;
    const maxLeft = Math.max(0, window.innerWidth - this.assistDragSize.width);
    const maxTop = Math.max(0, window.innerHeight - this.assistDragSize.height);
    this.assistPosition = {
      left: Math.min(Math.max(0, event.clientX - this.assistDragOffset.x), maxLeft),
      top: Math.min(Math.max(0, event.clientY - this.assistDragOffset.y), maxTop),
    };
    this.changeDetector.markForCheck();
  }

  private stopAssistDrag(): void {
    this.isAssistDragging = false;
    document.removeEventListener('pointermove', this.assistPointerMove);
    document.removeEventListener('pointerup', this.assistPointerUp);
  }

  ngOnDestroy(): void {
    this.closeIrAssist();
    this.stopAssistDrag();
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
