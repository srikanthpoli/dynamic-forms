import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { apiConfig } from '../config/api.config';

export interface TpsIr {
  id: string;
  ir_number: string;
  customer_name: string;
  uen?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  tin?: string | null;
  address?: string | null;
  status: string;
  priority: string;
  onboarding_type?: string | null;
  risk_rating?: string | null;
}

export interface TpsIrAssistResponse {
  assistant_message: string;
  published_forms?: TpsPublishedForm[];
  pending_form?: TpsPublishedForm | null;
}

export interface TpsPublishedFormField {
  name?: string;
  label?: string;
  validation_rules?: Record<string, unknown>;
}

export interface TpsPublishedForm {
  form_id: string;
  version_id: string;
  title: string;
  version_number: string;
  fields: TpsPublishedFormField[];
}

export interface SubmissionEvent {
  event_type: string;
  actor_type: string;
  created_at?: string | null;
  details?: Record<string, unknown>;
}

export interface IrForm {
  id: string;
  ir_id: string;
  form_id: string;
  form_version_id: string;
  form_title: string;
  version_number: string;
  status: string;
  required: boolean;
  display_order: number;
  released_at?: string | null;
  submission_id?: string | null;
  form_snapshot?: { layout_tree?: Array<{ order: number; column_span?: number | null; field?: import('../models/field.models').FieldTemplate | null }> } | null;
  submission_data?: Record<string, unknown> | null;
  event_history?: SubmissionEvent[];
}

@Injectable({ providedIn: 'root' })
export class TpsApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${apiConfig.baseUrl}/tps`;

  listIrs(): Observable<TpsIr[]> {
    return this.http.get<TpsIr[]>(`${this.baseUrl}/irs`);
  }

  getIr(irNumber: string): Observable<TpsIr> {
    return this.http.get<TpsIr>(`${this.baseUrl}/irs/${encodeURIComponent(irNumber)}`);
  }

  updateIr(irNumber: string, ir: TpsIr): Observable<TpsIr> {
    const { id, ir_number, ...payload } = ir;
    return this.http.put<TpsIr>(`${this.baseUrl}/irs/${encodeURIComponent(irNumber)}`, payload);
  }

  loadIrAssistantContext(irNumber: string, sessionId: string, irContext: TpsIr): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/assist/context`, {
      session_id: sessionId,
      ir_context: irContext,
    });
  }

  askIrAssistantSession(irNumber: string, sessionId: string, prompt: string): Observable<TpsIrAssistResponse> {
    return this.http.post<TpsIrAssistResponse>(`${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/assist`, {
      session_id: sessionId,
      prompt,
    });
  }

  assignFormToIr(irNumber: string, form: TpsPublishedForm): Observable<IrForm> {
    return this.http.post<IrForm>(`${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/forms`, {
      form_id: form.form_id,
      form_version_id: form.version_id,
      required: false,
      display_order: 0,
    });
  }

  listIrForms(irNumber: string): Observable<IrForm[]> {
    return this.http.get<IrForm[]>(`${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/forms`);
  }

  releaseIrForm(irNumber: string, irFormId: string): Observable<{ ir_form_id: string; submission_id: string; status: string }> {
    return this.http.post<{ ir_form_id: string; submission_id: string; status: string }>(
      `${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/forms/${irFormId}/release`, {},
    );
  }

  recallIrForm(irNumber: string, irFormId: string): Observable<{ ir_form_id: string; submission_id: string; status: string }> {
    return this.http.post<{ ir_form_id: string; submission_id: string; status: string }>(
      `${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/forms/${irFormId}/recall`, {},
    );
  }

  deleteIrForm(irNumber: string, irFormId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/forms/${irFormId}`);
  }

  saveIrFormSubmission(irNumber: string, irFormId: string, submissionData: Record<string, unknown>): Observable<IrForm> {
    return this.http.put<IrForm>(
      `${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/forms/${irFormId}/submission`,
      { submission_data: submissionData },
    );
  }

  submitIrForm(irNumber: string, irFormId: string): Observable<{ ir_form_id: string; submission_id: string; status: string }> {
    return this.http.post<{ ir_form_id: string; submission_id: string; status: string }>(
      `${this.baseUrl}/irs/${encodeURIComponent(irNumber)}/forms/${irFormId}/submit`, {},
    );
  }
}
