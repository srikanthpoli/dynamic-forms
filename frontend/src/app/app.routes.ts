import { Routes } from '@angular/router';
import { FieldBuilderPageComponent } from './features/field-builder/field-builder-page/field-builder-page';
import { FormBuilderPageComponent } from './features/form-builder/form-builder-page/form-builder-page';
import { PublishedLibraryPageComponent } from './features/published-library/published-library-page';
import { AdminPageComponent } from './features/admin/admin-page/admin-page';

export const routes: Routes = [
  { path: '', component: FieldBuilderPageComponent },
  { path: 'forms', component: FormBuilderPageComponent },
  { path: 'library', component: PublishedLibraryPageComponent },
  { path: 'admin', component: AdminPageComponent },
  { path: '**', redirectTo: '' },
];
