import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { FormBuildResponse, FormDefinition, FormDefinitionJson, FormVersion, PublishedForm } from '../models/form.models';
import { apiConfig } from '../config/api.config';
import { postEventStream, StreamEvent } from '../utils/event-stream';

@Injectable({ providedIn: 'root' })
export class FormBuilderApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = apiConfig.baseUrl;

  buildForm(sessionId: string, prompt: string, formContext?: FormDefinitionJson | null): Observable<FormBuildResponse> {
    return this.http.post<FormBuildResponse>(`${this.baseUrl}/forms/build`, {
      session_id: sessionId,
      prompt,
      form_context: formContext ?? null,
    });
  }

  buildFormStream(sessionId: string, prompt: string, formContext?: FormDefinitionJson | null): Observable<StreamEvent<FormBuildResponse>> {
    return postEventStream<FormBuildResponse>(`${this.baseUrl}/forms/build/stream`, {
      session_id: sessionId,
      prompt,
      form_context: formContext ?? null,
    });
  }

  createFormDefinition(title: string, description: string | null): Observable<FormDefinition> {
    return this.http.post<FormDefinition>(`${this.baseUrl}/forms/definitions`, { title, description });
  }

  listFormDefinitions(): Observable<FormDefinition[]> {
    return this.http.get<FormDefinition[]>(`${this.baseUrl}/forms/definitions`);
  }

  saveVersionFromDefinition(
    formId: string,
    versionBump: 'major' | 'minor' | 'patch',
    formDefinition: FormDefinitionJson,
  ): Observable<{ status: string; version_id: string; version: string }> {
    return this.http.post<{ status: string; version_id: string; version: string }>(
      `${this.baseUrl}/forms/${formId}/versions/from-definition`,
      { version_bump: versionBump, form_definition: formDefinition },
    );
  }

  updateDraftVersion(
    formId: string,
    versionNumber: string,
    formDefinition: FormDefinitionJson,
  ): Observable<{ status: string; version_id: string; version: string }> {
    return this.http.put<{ status: string; version_id: string; version: string }>(
      `${this.baseUrl}/forms/${formId}/versions/${versionNumber}/draft`,
      { form_definition: formDefinition },
    );
  }

  publishVersion(formId: string, versionId: string): Observable<{ status: string; version_id: string }> {
    return this.http.post<{ status: string; version_id: string }>(
      `${this.baseUrl}/forms/${formId}/versions/${versionId}/publish`,
      {},
    );
  }

  deleteVersion(formId: string, versionId: string): Observable<{ status: string; version_id: string }> {
    return this.http.delete<{ status: string; version_id: string }>(
      `${this.baseUrl}/forms/${formId}/versions/${versionId}`,
    );
  }

  listPublishedForms(): Observable<PublishedForm[]> {
    return this.http.get<PublishedForm[]>(`${this.baseUrl}/forms/published`);
  }

  listFormVersions(formId: string): Observable<FormVersion[]> {
    return this.http.get<FormVersion[]>(`${this.baseUrl}/forms/${formId}/versions`);
  }
}
