import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { NgIf } from '@angular/common';
import { forkJoin } from 'rxjs';
import { FieldTemplate } from '../../core/models/field.models';
import { PublishedForm } from '../../core/models/form.models';
import { FieldBuilderApiService } from '../../core/services/field-builder-api.service';
import { FormBuilderApiService } from '../../core/services/form-builder-api.service';
import { FieldLivePreviewComponent } from '../field-builder/field-live-preview/field-live-preview';

@Component({
  selector: 'app-published-library-page',
  standalone: true,
  imports: [NgIf, FieldLivePreviewComponent],
  templateUrl: './published-library-page.html',
  styleUrl: './published-library-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PublishedLibraryPageComponent implements OnInit {
  private readonly fieldApi = inject(FieldBuilderApiService);
  private readonly formApi = inject(FormBuilderApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);

  fields: FieldTemplate[] = [];
  forms: PublishedForm[] = [];
  selectedForm: PublishedForm | null = null;
  isLoading = true;
  error = '';

  ngOnInit(): void {
    forkJoin({ fields: this.fieldApi.listFields(), forms: this.formApi.listPublishedForms() }).subscribe({
      next: result => {
        this.fields = result.fields;
        this.forms = result.forms;
        this.selectedForm = this.forms[0] ?? null;
        this.isLoading = false;
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.isLoading = false;
        this.error = 'The published library could not be loaded. Check that the backend is running.';
        this.changeDetector.markForCheck();
      },
    });
  }

  selectForm(form: PublishedForm): void {
    this.selectedForm = form;
  }

  sortedLayout(form: PublishedForm): PublishedForm['layout_tree'] {
    return [...form.layout_tree].sort((a, b) => a.order - b.order);
  }
}
