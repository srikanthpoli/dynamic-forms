import { Routes } from '@angular/router';
import { FieldBuilderPageComponent } from './features/field-builder/field-builder-page/field-builder-page';
import { FormBuilderPageComponent } from './features/form-builder/form-builder-page/form-builder-page';

export const routes: Routes = [
  { path: '', component: FieldBuilderPageComponent },
  { path: 'forms', component: FormBuilderPageComponent },
  { path: '**', redirectTo: '' },
];
