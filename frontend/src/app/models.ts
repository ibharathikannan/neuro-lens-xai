// Shapes of the data exchanged with the FastAPI backend.

/** Class name as returned by the backend (brain tumor: glioma · meningioma · notumor · pituitary). */
export type TumorClass = string;

export const CLASS_LABELS: Record<string, string> = {
  glioma: 'Glioma',
  meningioma: 'Meningioma',
  notumor: 'No tumor',
  pituitary: 'Pituitary',
  benign: 'Benign',
  malignant: 'Malignant',
};

export const CLASS_COLORS: Record<string, string> = {
  glioma: '#d9534f',
  meningioma: '#e0a030',
  notumor: '#3a9d6b',
  pituitary: '#6f5bc4',
  benign: '#3a9d6b',
  malignant: '#d9534f',
};

const FALLBACK_COLORS = ['#1f3864', '#e0a030', '#6f5bc4', '#3a9d6b', '#d9534f', '#3b6fb6'];

export function classLabel(c: string): string {
  return CLASS_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1).replace(/_/g, ' ');
}

export function classColor(c: string, index = 0): string {
  return CLASS_COLORS[c] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

// ---------- Auth (backend: /api/auth) ----------

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: 'admin' | 'clinician' | string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface LoginRequest { email: string; password: string; }
export interface RegisterRequest { full_name: string; email: string; password: string; }

// ---------- Clinical data ----------

export type ReviewStatus = 'Awaiting review' | 'Reviewed' | 'Flagged';

export interface Patient {
  id: string;
  age: number;
  sex: 'F' | 'M';
  registered: string;
  scans: number;
  last_scan: string;
  last_result: TumorClass | null;
  status: ReviewStatus;
  referring_unit?: string;
  notes?: string;
}

export interface StoredFile { path: string; type: string; size: string; uploaded: string; }

/** Position of the highlighted region in a (placeholder) scan image, as fractions of the image. */
export interface Lesion { x: number; y: number; r: number; }

export interface Scan {
  id: string;
  patient_id: string;
  date: string;
  prediction: TumorClass;
  confidence: number;                          // 0–1
  probabilities: Record<TumorClass, number>;   // 0–1
  status: ReviewStatus;
  image_url?: string;                          // Azure Blob SAS URL (real backend)
  gradcam_url?: string;
  report_url?: string;
  report_path?: string;
  scan_date?: string;
  sequence?: string;
  model_version: string;
  inference_seconds: number;
  explanation: string;
  similar_agreement?: string;                  // e.g. "5 / 5"
  lesion?: Lesion;                             // demo data only
}

export interface PatientDetail extends Patient { history: Scan[]; files: StoredFile[]; }

export interface SimilarCase {
  case_id: string;
  label: TumorClass;
  similarity: number;       // 0–100
  source: 'reference' | 'patient';
  patient_id?: string;
  image_url?: string;
  gradcam_url?: string;
  lesion?: Lesion;
}

export interface SimilarResult {
  query: Scan;
  search_space: string;
  method: string;
  k: number;
  agreement: string;
  cases: SimilarCase[];
}

export interface Comparison {
  query: Scan;
  reference: SimilarCase & { probabilities: Record<TumorClass, number>; source_dataset: string };
  similarity: number;
  same_class: boolean;
  heatmap_iou: number;
  focus_region: string;
  focus_distance_px: number;
  lesion_extent: string;
  explanation: string[];
}

export interface Report {
  id: string;
  patient_id: string;
  scan_id: string;
  result: TumorClass;
  created: string;
  blob_path: string;
  size: string;
}

export interface DashboardSummary {
  patients: number;
  patients_this_month: number;
  scans: number;
  scans_this_month: number;
  reports: number;
  avg_inference_seconds: number;
  weekly: { week: string; counts: Record<TumorClass, number> }[];
  distribution: Record<TumorClass, number>;   // percentages
  low_confidence: number;
  recent: Scan[];
}

export interface ServiceStatus { name: string; detail: string; status: string; healthy: boolean; }

export interface ModelRow {
  model: string; track: 'A' | 'B'; config: string; accuracy: number; macro_f1: number;
  glioma_recall: number; params: string; latency_ms: number; selected: boolean;
}

export interface SystemInfo {
  model: { name: string; source: string; revision: string; parameters: string; input: string; classes: string; explanation: string; loaded: string; };
  services: ServiceStatus[];
  comparison: ModelRow[];
  comparison_is_placeholder: boolean;
}

export interface ClassifyRequest {
  patient_id: string;
  scan_date: string;
  sequence: string;
  notes: string;
  file: File;
}
