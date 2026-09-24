import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { FieldGenerateResponse, FieldTemplate } from '../models/field.models';

@Injectable({ providedIn: 'root' })
export class FieldBuilderApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://127.0.0.1:8000/api';

  generateField(sessionId: string, prompt: string, fieldContext: FieldTemplate | null = null): Observable<FieldGenerateResponse> {
    return this.http.post<FieldGenerateResponse>(`${this.baseUrl}/fields/generate`, {
      session_id: sessionId,
      prompt,
      field_context: fieldContext,
    });
  }

  publishField(field: FieldTemplate): Observable<FieldTemplate> {
    return this.http.post<FieldTemplate>(`${this.baseUrl}/fields/publish`, field);
  }

  overrideField(fieldId: string, field: FieldTemplate): Observable<FieldTemplate> {
    const { id, assistant_message, ...definition } = field;
    return this.http.put<FieldTemplate>(`${this.baseUrl}/fields/${fieldId}`, definition);
  }

  deleteField(fieldId: string): Observable<{ status: string; field_id: string }> {
    return this.http.delete<{ status: string; field_id: string }>(`${this.baseUrl}/fields/${fieldId}`);
  }

  listFields(): Observable<FieldTemplate[]> {
    return this.http.get<FieldTemplate[]>(`${this.baseUrl}/fields/`);
  }
}
