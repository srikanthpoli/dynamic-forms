import { Routes } from '@angular/router';
import { FieldBuilderPageComponent } from './features/field-builder/field-builder-page/field-builder-page';
import { FormBuilderPageComponent } from './features/form-builder/form-builder-page/form-builder-page';
import { PublishedLibraryPageComponent } from './features/published-library/published-library-page';
import { AdminPageComponent } from './features/admin/admin-page/admin-page';
import { TpsPageComponent } from './features/tps/tps-page/tps-page';
import { TpsDetailPageComponent } from './features/tps/tps-detail-page/tps-detail-page';

export const routes: Routes = [
  { path: '', component: FieldBuilderPageComponent },
  { path: 'forms', component: FormBuilderPageComponent },
  { path: 'library', component: PublishedLibraryPageComponent },
  { path: 'admin', component: AdminPageComponent },
  { path: 'tps', component: TpsPageComponent },
  { path: 'tps/irs/:irNumber', component: TpsDetailPageComponent },
  { path: '**', redirectTo: '' },
];
