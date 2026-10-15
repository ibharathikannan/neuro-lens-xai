import { Routes } from '@angular/router';

import { adminGuard, authGuard, guestGuard } from './auth.guard';
import { Shell } from './layout/shell';

export const routes: Routes = [
  { path: 'login', canActivate: [guestGuard], loadComponent: () => import('./pages/login/login').then((m) => m.Login) },
  { path: 'register', canActivate: [guestGuard], loadComponent: () => import('./pages/register/register').then((m) => m.Register) },
  {
    path: '',
    component: Shell,
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', data: { title: 'Dashboard', crumb: 'Overview' },
        loadComponent: () => import('./pages/dashboard/dashboard').then((m) => m.Dashboard) },
      { path: 'patients', data: { title: 'Patients', crumb: 'Patient records' },
        loadComponent: () => import('./pages/patients/patients').then((m) => m.Patients) },
      { path: 'patients/:id', data: { title: 'Patient', crumb: 'Patients › Patient detail' },
        loadComponent: () => import('./pages/patient-detail/patient-detail').then((m) => m.PatientDetailPage) },
      { path: 'new-scan', data: { title: 'New Classification', crumb: 'Classify a new MRI scan' },
        loadComponent: () => import('./pages/new-scan/new-scan').then((m) => m.NewScan) },
      { path: 'scans/:id', data: { title: 'Classification Result', crumb: 'Scans › Result' },
        loadComponent: () => import('./pages/result/result').then((m) => m.Result) },
      { path: 'studies/:id', data: { title: 'Multi-slice Result', crumb: 'Scans › Multi-slice result' },
        loadComponent: () => import('./pages/study/study').then((m) => m.StudyPage) },
      { path: 'scans/:id/similar', data: { title: 'Similar Cases', crumb: 'Scans › Similar cases' },
        loadComponent: () => import('./pages/similar/similar').then((m) => m.Similar) },
      { path: 'scans/:id/compare/:caseId', data: { title: 'Case Comparison', crumb: 'Similar cases › Comparison' },
        loadComponent: () => import('./pages/compare/compare').then((m) => m.Compare) },
      { path: 'similar', data: { title: 'Similar Cases', crumb: 'Scans › Similar cases' },
        loadComponent: () => import('./pages/similar/similar').then((m) => m.Similar) },
      { path: 'reports', data: { title: 'Reports', crumb: 'Generated reports · Azure Blob Storage' },
        loadComponent: () => import('./pages/reports/reports').then((m) => m.Reports) },
      { path: 'system', data: { title: 'Model & System', crumb: 'Deployed model, evaluation and service status' },
        loadComponent: () => import('./pages/model-system/model-system').then((m) => m.ModelSystem) },
      { path: 'account', data: { title: 'My Account', crumb: 'Account › Change password' },
        loadComponent: () => import('./pages/account/account').then((m) => m.Account) },
      { path: 'users', canActivate: [adminGuard], data: { title: 'Users', crumb: 'Administration › Team accounts' },
        loadComponent: () => import('./pages/users/users').then((m) => m.Users) },
    ],
  },
  { path: '**', redirectTo: '' },
];
