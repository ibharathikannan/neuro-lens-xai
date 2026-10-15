import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, delay, map, of, tap, throwError, catchError } from 'rxjs';

import { environment } from '../environments/environment';
import {
  AuthSettings, ClassifyRequest, Comparison, DashboardSummary, LoginRequest, NewUserRequest, PasswordChangeRequest,
  Patient, PatientDetail, RegisterRequest, Report, Scan, SimilarResult, Study, StudyRequest, SystemInfo, TokenResponse, User, UserUpdate,
} from './models';
import * as mock from './mock-data';

const TOKEN_KEY = 'neurolens_token';
const USER_KEY = 'neurolens_user';

/**
 * The ONLY place in the frontend that talks to the backend.
 * Every page calls a method here; nothing else uses HttpClient directly.
 *
 * Backend routes (FastAPI, code/backend):
 *   POST /api/auth/register      create account            (implemented)
 *   POST /api/auth/login         log in, returns JWT        (implemented)
 *   GET  /api/auth/me            current user               (implemented)
 *   GET  /api/auth/settings      is self-registration open  (implemented)
 *   POST /api/auth/change-password                          (implemented)
 *   GET/POST /api/auth/users, PATCH /api/auth/users/{id}    administrators manage accounts (implemented)
 *   GET  /api/health             service status             (implemented)
 *   GET/POST /api/patients, GET /api/patients/{id}                     (implemented)
 *   POST /api/scans/classify, GET /api/scans/{id}, POST .../review      (implemented)
 *   GET  /api/scans/{id}/report  (DOCX), /api/reports, /api/dashboard/summary, /api/system/model  (implemented)
 *   GET  /api/scans/{id}/similar, /api/scans/{id}/compare/{caseId}      (implemented — vector search over confirmed cases)
 *   POST /api/studies/classify (2–10 slices), GET /api/studies/{id}, POST .../review, GET .../report   (implemented — multi-slice)
 * While environment.useMockData is true, the clinical calls return demo data from mock-data.ts instead.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly api = environment.apiUrl;

  /** The logged-in user (null when logged out). */
  readonly currentUser = signal<User | null>(this.readStoredUser());
  readonly isAdmin = computed(() => this.currentUser()?.role === 'admin');

  // ======================================================================
  // Authentication
  // ======================================================================

  login(body: LoginRequest): Observable<User> {
    return this.http.post<TokenResponse>(`${this.api}/auth/login`, body).pipe(
      tap((res) => this.storeSession(res)),
      map((res) => res.user),
      catchError((err) => this.fail(err, false)),
    );
  }

  register(body: RegisterRequest): Observable<User> {
    return this.http.post<TokenResponse>(`${this.api}/auth/register`, body).pipe(
      tap((res) => this.storeSession(res)),
      map((res) => res.user),
      catchError((err) => this.fail(err, false)),
    );
  }

  /** Refreshes the user details from the backend (also confirms the token is still valid). */
  loadCurrentUser(): Observable<User> {
    return this.http.get<User>(`${this.api}/auth/me`, { headers: this.authHeaders() }).pipe(
      tap((user) => {
        this.currentUser.set(user);
        this.store(USER_KEY, JSON.stringify(user));
      }),
      catchError((err) => this.fail(err)),
    );
  }

  /** Public: whether visitors may create their own account (administrators can always add users). */
  getAuthSettings(): Observable<AuthSettings> {
    return this.http.get<AuthSettings>(`${this.api}/auth/settings`).pipe(catchError((err) => this.fail(err, false)));
  }

  /** Changes the password; the backend signs out other sessions and returns a fresh token for this one. */
  changePassword(body: PasswordChangeRequest): Observable<User> {
    return this.http.post<TokenResponse>(`${this.api}/auth/change-password`, body, { headers: this.authHeaders() }).pipe(
      tap((res) => this.storeSession(res)),
      map((res) => res.user),
      catchError((err) => this.fail(err)),
    );
  }

  // ---------- User management (administrators) ----------

  getUsers(): Observable<User[]> {
    return this.get<User[]>('/auth/users');
  }

  createUser(body: NewUserRequest): Observable<User> {
    return this.http.post<User>(`${this.api}/auth/users`, body, { headers: this.authHeaders() })
      .pipe(catchError((err) => this.fail(err)));
  }

  updateUser(id: string, body: UserUpdate): Observable<User> {
    return this.http.patch<User>(`${this.api}/auth/users/${encodeURIComponent(id)}`, body, { headers: this.authHeaders() })
      .pipe(catchError((err) => this.fail(err)));
  }

  logout(): void {
    this.remove(TOKEN_KEY);
    this.remove(USER_KEY);
    this.currentUser.set(null);
    this.router.navigate(['/login']);
  }

  /** True when a token is stored and has not expired yet. */
  isLoggedIn(): boolean {
    const token = this.read(TOKEN_KEY);
    if (!token) return false;
    try {
      const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  }

  // ======================================================================
  // System
  // ======================================================================

  getHealth(): Observable<{ status: string; database: string }> {
    return this.http.get<{ status: string; database: string }>(`${this.api}/health`).pipe(
      catchError((err) => this.fail(err, false)),
    );
  }

  getSystemInfo(): Observable<SystemInfo> {
    return this.useMock(mock.SYSTEM) ?? this.get<SystemInfo>('/system/model');
  }

  // ======================================================================
  // Dashboard & patients
  // ======================================================================

  getDashboardSummary(): Observable<DashboardSummary> {
    return this.useMock(mock.DASHBOARD) ?? this.get<DashboardSummary>('/dashboard/summary');
  }

  getPatients(search = ''): Observable<Patient[]> {
    if (environment.useMockData) {
      const term = search.trim().toLowerCase();
      return this.mock(mock.PATIENTS.filter((p) => !term || p.id.toLowerCase().includes(term)));
    }
    return this.get<Patient[]>('/patients', { search });
  }

  getPatient(id: string): Observable<PatientDetail> {
    return this.useMock(mock.patientDetail(id)) ?? this.get<PatientDetail>(`/patients/${encodeURIComponent(id)}`);
  }

  createPatient(body: { age: number; sex: 'F' | 'M'; referring_unit: string; notes: string }): Observable<Patient> {
    if (environment.useMockData) return this.mock(mock.newPatient(body));
    return this.http.post<Patient>(`${this.api}/patients`, body, { headers: this.authHeaders() })
      .pipe(catchError((err) => this.fail(err)));
  }

  // ======================================================================
  // Scans: classification, similar cases, comparison
  // ======================================================================

  /** Uploads an MRI slice; the backend classifies it, builds the heatmap and report, and stores everything. */
  classifyScan(req: ClassifyRequest): Observable<Scan> {
    if (environment.useMockData) return this.mock(mock.SCAN_RESULT, 900);
    const form = new FormData();
    form.append('file', req.file);
    form.append('patient_id', req.patient_id);
    form.append('scan_date', req.scan_date);
    form.append('sequence', req.sequence);
    form.append('notes', req.notes);
    return this.http.post<Scan>(`${this.api}/scans/classify`, form, { headers: this.authHeaders() })
      .pipe(catchError((err) => this.fail(err)));
  }

  /** Uploads 2–10 slices of the same scan; each is classified separately and the results are combined. */
  classifyStudy(req: StudyRequest): Observable<Study> {
    if (environment.useMockData) return this.mock(mock.STUDY, 1500);
    const form = new FormData();
    for (const f of req.files) form.append('files', f);
    form.append('patient_id', req.patient_id);
    form.append('scan_date', req.scan_date);
    form.append('sequence', req.sequence);
    form.append('notes', req.notes);
    return this.http.post<Study>(`${this.api}/studies/classify`, form, { headers: this.authHeaders() })
      .pipe(catchError((err) => this.fail(err)));
  }

  getStudy(id: string): Observable<Study> {
    return this.useMock(mock.STUDY) ?? this.get<Study>(`/studies/${encodeURIComponent(id)}`);
  }

  markStudyReviewed(id: string): Observable<Study> {
    if (environment.useMockData) return this.mock({ ...mock.STUDY, status: 'Reviewed' as const });
    return this.http.post<Study>(`${this.api}/studies/${encodeURIComponent(id)}/review`, {}, { headers: this.authHeaders() })
      .pipe(catchError((err) => this.fail(err)));
  }

  getScan(id: string): Observable<Scan> {
    return this.useMock(mock.scanById(id)) ?? this.get<Scan>(`/scans/${encodeURIComponent(id)}`);
  }

  /** k defaults to the backend's SIMILAR_K setting (chosen in the notebook, Section 9). */
  getSimilarCases(scanId: string, k?: number): Observable<SimilarResult> {
    return this.useMock(mock.similarFor(scanId))
      ?? this.get<SimilarResult>(`/scans/${encodeURIComponent(scanId)}/similar`, k ? { k: String(k) } : {});
  }

  compareCases(scanId: string, caseId: string): Observable<Comparison> {
    return this.useMock(mock.comparison(scanId, caseId))
      ?? this.get<Comparison>(`/scans/${encodeURIComponent(scanId)}/compare/${encodeURIComponent(caseId)}`);
  }

  markReviewed(scanId: string): Observable<Scan> {
    if (environment.useMockData) return this.mock({ ...mock.scanById(scanId), status: 'Reviewed' as const });
    return this.http.post<Scan>(`${this.api}/scans/${encodeURIComponent(scanId)}/review`, {}, { headers: this.authHeaders() })
      .pipe(catchError((err) => this.fail(err)));
  }

  // ======================================================================
  // Reports
  // ======================================================================

  getReports(): Observable<Report[]> {
    return this.useMock(mock.REPORTS) ?? this.get<Report[]>('/reports');
  }

  /**
   * Downloads a scan's report. The request carries the login token, so the file is fetched here and saved
   * through a temporary link. Returns false in demo-data mode (nothing to download).
   */
  downloadReport(scanId: string): Observable<boolean> {
    return this.downloadFile(`/scans/${encodeURIComponent(scanId)}/report`, `NeuroLens_${scanId}.docx`);
  }

  /** Downloads a multi-slice study's report (combined result, per-slice table, slices and heatmaps). */
  downloadStudyReport(studyId: string): Observable<boolean> {
    return this.downloadFile(`/studies/${encodeURIComponent(studyId)}/report`, `NeuroLens_${studyId}.docx`);
  }

  private downloadFile(path: string, fallbackName: string): Observable<boolean> {
    if (environment.useMockData) return this.mock(false);
    return this.http.get(`${this.api}${path}`, {
      headers: this.authHeaders(), responseType: 'blob', observe: 'response',
    }).pipe(
      map((res) => {
        const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? fallbackName;
        const url = URL.createObjectURL(res.body as Blob);
        const a = Object.assign(document.createElement('a'), { href: url, download: name });
        a.click();
        URL.revokeObjectURL(url);
        return true;
      }),
      catchError((err) => this.fail(err)),
    );
  }

  // ======================================================================
  // Internal helpers
  // ======================================================================

  private get<T>(path: string, params: Record<string, string> = {}): Observable<T> {
    return this.http.get<T>(`${this.api}${path}`, { headers: this.authHeaders(), params })
      .pipe(catchError((err) => this.fail(err)));
  }

  private authHeaders(): HttpHeaders {
    const token = this.read(TOKEN_KEY);
    return token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : new HttpHeaders();
  }

  /** Returns demo data when mock mode is on, otherwise null (so the caller falls through to the real request). */
  private useMock<T>(value?: T): Observable<T> | null {
    if (!environment.useMockData) return null;
    return this.mock(value as T);
  }

  private mock<T>(value: T, ms = 250): Observable<T> {
    return of(value === undefined ? value : structuredClone(value)).pipe(delay(ms));
  }

  /** Converts an HTTP error into a readable message; a 401 on a protected call logs the user out. */
  private fail(err: HttpErrorResponse, logoutOn401 = true): Observable<never> {
    if (err.status === 401 && logoutOn401) this.logout();
    let message = 'Something went wrong. Please try again.';
    if (err.status === 0) message = 'Cannot reach the server. Is the backend running?';
    else if (typeof err.error?.detail === 'string') message = err.error.detail;
    else if (Array.isArray(err.error?.detail)) {
      message = err.error.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join(' ');
    }
    return throwError(() => new Error(message));
  }

  private storeSession(res: TokenResponse): void {
    this.store(TOKEN_KEY, res.access_token);
    this.store(USER_KEY, JSON.stringify(res.user));
    this.currentUser.set(res.user);
  }

  private readStoredUser(): User | null {
    try {
      const raw = this.read(USER_KEY);
      return raw && this.isLoggedIn() ? (JSON.parse(raw) as User) : null;
    } catch {
      return null;
    }
  }

  // Storage can be unavailable (private mode, blocked site data) — never let that break the app.
  private read(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
  }
  private store(key: string, value: string): void {
    try { localStorage.setItem(key, value); } catch { /* ignore */ }
  }
  private remove(key: string): void {
    try { localStorage.removeItem(key); } catch { /* ignore */ }
  }
}
