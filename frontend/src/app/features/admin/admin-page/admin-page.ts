import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { Observable, finalize, map } from 'rxjs';
import { AdminApiService } from '../../../core/services/admin-api.service';
import { IndexRefreshResponse } from '../../../core/services/admin-api.service';

interface AdminAction {
  key: 'capabilities' | 'fields' | 'forms' | 'all' | 'generate';
  title: string;
  description: string;
  action: string;
  tone: 'blue' | 'green' | 'red';
}

@Component({
  selector: 'app-admin-page',
  standalone: true,
  templateUrl: './admin-page.html',
  styleUrl: './admin-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminPageComponent implements OnInit {
  private readonly api = inject(AdminApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);

  readonly actions: AdminAction[] = [
    {
      key: 'capabilities',
      title: 'Angular capabilities',
      description: 'Rebuild the index from angular_material_capabilities.json.',
      action: 'Refresh index',
      tone: 'blue',
    },
    {
      key: 'fields',
      title: 'Published fields',
      description: 'Re-index the field definitions currently published in PostgreSQL.',
      action: 'Refresh index',
      tone: 'green',
    },
    {
      key: 'forms',
      title: 'Published forms',
      description: 'Re-index published form versions and their field snapshots.',
      action: 'Refresh index',
      tone: 'green',
    },
    {
      key: 'all',
      title: 'All indexes',
      description: 'Rebuild capabilities, published fields, and published forms together.',
      action: 'Refresh everything',
      tone: 'red',
    },
    {
      key: 'generate',
      title: 'Regenerate capabilities',
      description: 'Fetch official Angular Material docs, regenerate the registry, and refresh capabilities.',
      action: 'Regenerate with LLM',
      tone: 'blue',
    },
  ];

  runningKey: AdminAction['key'] | null = null;
  lastMessage = '';
  error = '';

  ngOnInit(): void {}

  run(action: AdminAction): void {
    if (this.runningKey) return;
    this.runningKey = action.key;
    this.lastMessage = '';
    this.error = '';

    let request: Observable<IndexRefreshResponse> = action.key === 'capabilities'
      ? this.api.refreshCapabilitiesIndex()
      : action.key === 'fields'
        ? this.api.refreshPublishedFieldsIndex()
        : action.key === 'forms'
          ? this.api.refreshPublishedFormsIndex()
          : action.key === 'all'
            ? this.api.refreshAllIndexes()
            : this.api.regenerateCapabilities().pipe(map(response => ({
              status: response.status,
              documents_indexed: response.components.length,
            })));

    request.pipe(finalize(() => {
      this.runningKey = null;
      this.changeDetector.markForCheck();
    })).subscribe({
      next: response => {
        this.lastMessage = this.formatResponse(action, response);
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.error?.detail ?? `The ${action.title.toLowerCase()} operation failed.`;
        this.changeDetector.markForCheck();
      },
    });
  }

  private formatResponse(action: AdminAction, response: { documents_indexed?: number; indexes?: Record<string, number> }): string {
    if (response.indexes) {
      return `All indexes refreshed: ${Object.entries(response.indexes).map(([name, count]) => `${name} (${count})`).join(', ')}.`;
    }
    if (typeof response.documents_indexed === 'number') {
      return `${action.title} refreshed: ${response.documents_indexed} document(s) indexed.`;
    }
    return `${action.title} completed successfully.`;
  }
}
