import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { apiConfig } from '../config/api.config';

export interface IndexRefreshResponse {
  status: string;
  index?: string;
  documents_indexed?: number;
  indexes?: Record<string, number>;
}

export interface CapabilityGenerationResponse {
  status: string;
  components: string[];
  registry: Record<string, unknown>;
}

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${apiConfig.baseUrl}/spec`;

  refreshCapabilitiesIndex(): Observable<IndexRefreshResponse> {
    return this.http.post<IndexRefreshResponse>(`${this.baseUrl}/refresh`, {});
  }

  refreshPublishedFieldsIndex(): Observable<IndexRefreshResponse> {
    return this.http.post<IndexRefreshResponse>(`${this.baseUrl}/refresh-fields-index`, {});
  }

  refreshPublishedFormsIndex(): Observable<IndexRefreshResponse> {
    return this.http.post<IndexRefreshResponse>(`${this.baseUrl}/refresh-forms-index`, {});
  }

  refreshAllIndexes(): Observable<IndexRefreshResponse> {
    return this.http.post<IndexRefreshResponse>(`${this.baseUrl}/refresh-all-indexes`, {});
  }

  regenerateCapabilities(): Observable<CapabilityGenerationResponse> {
    return this.http.post<CapabilityGenerationResponse>(`${this.baseUrl}/generate-capabilities`, {});
  }
}
