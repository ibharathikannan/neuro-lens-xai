// Demo data, used ONLY by service.ts while environment.useMockData is true.
// Every patient here is synthetic. Delete this file once all backend routes exist.
import {
  Comparison, DashboardSummary, Patient, PatientDetail, Report, Scan, SimilarResult, Study, SystemInfo, TumorClass,
} from './models';

const probs = (g: number, m: number, p: number, n: number): Record<TumorClass, number> =>
  ({ glioma: g, meningioma: m, pituitary: p, notumor: n });

const MODEL = 'Fibonacci-Net · HF rev a1b2c3d';

function scan(id: string, patient: string, date: string, cls: TumorClass, conf: number,
              p: Record<TumorClass, number>, status: Scan['status'], agreement: string,
              lesion = { x: 0.64, y: 0.36, r: 0.11 }): Scan {
  return {
    id, patient_id: patient, date, prediction: cls, confidence: conf, probabilities: p, status,
    model_version: MODEL, inference_seconds: 0.38, similar_agreement: agreement, lesion,
    report_path: `neurolens-patients/${patient}/${id}/report.pdf`,
    explanation: cls === 'notumor'
      ? 'No region stands out to the model, and the most similar confirmed cases show no tumor.'
      : `The model's attention concentrates on the bright, irregular region in the upper right of the image (red). ` +
        `${agreement.split(' ')[0]} of the 5 most similar confirmed cases share this class, which supports the prediction.`,
  };
}

export const SCAN_RESULT = scan('S-2026-0342', 'P-0128', '27 Sep 2026, 10:42', 'glioma', 0.934, probs(0.934, 0.041, 0.019, 0.006), 'Awaiting review', '5 / 5');

const SCANS: Scan[] = [
  SCAN_RESULT,
  scan('S-2026-0341', 'P-0091', '27 Sep 2026, 09:15', 'meningioma', 0.881, probs(0.07, 0.881, 0.03, 0.019), 'Awaiting review', '4 / 5', { x: 0.34, y: 0.33, r: 0.1 }),
  scan('S-2026-0340', 'P-0127', '26 Sep 2026, 16:03', 'notumor', 0.979, probs(0.006, 0.009, 0.006, 0.979), 'Reviewed', '5 / 5', { x: 0.5, y: 0.5, r: 0 }),
  scan('S-2026-0339', 'P-0034', '26 Sep 2026, 14:27', 'pituitary', 0.642, probs(0.12, 0.2, 0.642, 0.038), 'Flagged', '3 / 5', { x: 0.5, y: 0.62, r: 0.08 }),
  scan('S-2026-0338', 'P-0126', '26 Sep 2026, 11:50', 'glioma', 0.816, probs(0.816, 0.11, 0.05, 0.024), 'Reviewed', '4 / 5', { x: 0.6, y: 0.4, r: 0.12 }),
  scan('S-2026-0217', 'P-0091', '14 Aug 2026', 'meningioma', 0.917, probs(0.04, 0.917, 0.03, 0.013), 'Reviewed', '5 / 5', { x: 0.35, y: 0.34, r: 0.1 }),
  scan('S-2026-0158', 'P-0091', '02 Aug 2026', 'meningioma', 0.853, probs(0.08, 0.853, 0.05, 0.017), 'Reviewed', '4 / 5', { x: 0.36, y: 0.35, r: 0.1 }),
];

export function scanById(id: string): Scan {
  return SCANS.find((s) => s.id === id) ?? { ...SCAN_RESULT, id };
}

export const PATIENTS: Patient[] = [
  { id: 'P-0128', age: 54, sex: 'F', registered: '27 Sep 2026', scans: 1, last_scan: '27 Sep 2026', last_result: 'glioma', status: 'Awaiting review' },
  { id: 'P-0127', age: 38, sex: 'M', registered: '26 Sep 2026', scans: 1, last_scan: '26 Sep 2026', last_result: 'notumor', status: 'Reviewed' },
  { id: 'P-0126', age: 61, sex: 'M', registered: '24 Sep 2026', scans: 2, last_scan: '26 Sep 2026', last_result: 'glioma', status: 'Reviewed' },
  { id: 'P-0125', age: 47, sex: 'F', registered: '22 Sep 2026', scans: 1, last_scan: '22 Sep 2026', last_result: 'meningioma', status: 'Reviewed' },
  { id: 'P-0124', age: 29, sex: 'F', registered: '21 Sep 2026', scans: 1, last_scan: '21 Sep 2026', last_result: 'pituitary', status: 'Reviewed' },
  { id: 'P-0091', age: 66, sex: 'F', registered: '02 Aug 2026', scans: 3, last_scan: '27 Sep 2026', last_result: 'meningioma', status: 'Awaiting review' },
  { id: 'P-0077', age: 43, sex: 'M', registered: '19 Jul 2026', scans: 2, last_scan: '11 Sep 2026', last_result: 'notumor', status: 'Reviewed' },
  { id: 'P-0034', age: 35, sex: 'M', registered: '06 May 2026', scans: 4, last_scan: '26 Sep 2026', last_result: 'pituitary', status: 'Flagged' },
  { id: 'P-0012', age: 58, sex: 'F', registered: '14 Mar 2026', scans: 2, last_scan: '30 Aug 2026', last_result: 'glioma', status: 'Reviewed' },
];

export function patientDetail(id: string): PatientDetail {
  const p = PATIENTS.find((x) => x.id === id) ?? PATIENTS[0];
  const history = SCANS.filter((s) => s.patient_id === p.id);
  const latest = history[0];
  return {
    ...p,
    referring_unit: 'Neurology Clinic B',
    notes: 'Headaches for 3 months; follow-up MRI requested to monitor a previously detected lesion.',
    history,
    files: latest ? [
      { path: `patients/${p.id}/${latest.id}/report.pdf`, type: 'Report', size: '412 KB', uploaded: latest.date.split(',')[0] },
      { path: `patients/${p.id}/${latest.id}/scan.jpg`, type: 'MRI image', size: '38 KB', uploaded: latest.date.split(',')[0] },
      { path: `patients/${p.id}/${latest.id}/gradcam.png`, type: 'Heatmap', size: '61 KB', uploaded: latest.date.split(',')[0] },
    ] : [],
  };
}

export function newPatient(body: { age: number; sex: 'F' | 'M'; referring_unit: string; notes: string }): Patient {
  return { id: 'P-0129', age: body.age, sex: body.sex, registered: 'Today', scans: 0, last_scan: '—', last_result: 'notumor', status: 'Awaiting review', referring_unit: body.referring_unit, notes: body.notes };
}

export const DASHBOARD: DashboardSummary = {
  patients: 128, patients_this_month: 12, scans: 342, scans_this_month: 37, reports: 336, avg_inference_seconds: 0.41,
  weekly: [[28, 9, 7, 6], [31, 8, 9, 7], [26, 10, 6, 8], [35, 9, 11, 8], [30, 12, 8, 9], [38, 11, 10, 10], [34, 10, 12, 9], [41, 13, 11, 12]]
    .map((w, i) => ({ week: `W${i + 1}`, counts: { glioma: w[0], meningioma: w[1], pituitary: w[2], notumor: w[3] } })),
  distribution: { glioma: 31, meningioma: 24, pituitary: 22, notumor: 23 },
  low_confidence: 9,
  recent: SCANS.slice(0, 5),
};

const SIMILAR = [
  { case_id: 'REF-02417', label: 'glioma' as TumorClass, similarity: 94.2, source: 'reference' as const, lesion: { x: 0.63, y: 0.37, r: 0.12 } },
  { case_id: 'REF-01188', label: 'glioma' as TumorClass, similarity: 91.8, source: 'reference' as const, lesion: { x: 0.6, y: 0.35, r: 0.1 } },
  { case_id: 'S-2026-0126', label: 'glioma' as TumorClass, similarity: 89.5, source: 'patient' as const, patient_id: 'P-0012', lesion: { x: 0.66, y: 0.4, r: 0.13 } },
  { case_id: 'REF-03095', label: 'glioma' as TumorClass, similarity: 87.1, source: 'reference' as const, lesion: { x: 0.58, y: 0.33, r: 0.09 } },
  { case_id: 'REF-00764', label: 'glioma' as TumorClass, similarity: 84.6, source: 'reference' as const, lesion: { x: 0.68, y: 0.43, r: 0.11 } },
];

export function similarFor(scanId: string): SimilarResult {
  return {
    query: scanById(scanId), search_space: '4,896 reference cases + 342 patient scans',
    method: 'Cosine similarity, MongoDB Atlas Vector Search', k: 5, agreement: '5 / 5', cases: SIMILAR,
  };
}

export function comparison(scanId: string, caseId: string): Comparison {
  const ref = SIMILAR.find((c) => c.case_id === caseId) ?? SIMILAR[0];
  return {
    query: scanById(scanId),
    reference: { ...ref, probabilities: probs(0.962, 0.021, 0.011, 0.006), source_dataset: 'Figshare' },
    similarity: ref.similarity, same_class: true, heatmap_iou: 0.68, focus_region: 'Upper right', focus_distance_px: 6, lesion_extent: 'similar',
    explanation: [
      `The model represents both scans with very similar internal features (${ref.similarity}% embedding similarity).`,
      'In both scans the model focuses on the same area: a bright, irregular region in the upper right of the image (heatmap overlap 68%).',
      `Both are classified as ${ref.label}; the reference case's diagnosis is confirmed in the source dataset.`,
      'The highlighted regions have a similar estimated size, suggesting lesions of comparable extent.',
    ],
  };
}

export const REPORTS: Report[] = [
  ['R-0336', 'P-0128', 'S-2026-0342', 'glioma', '27 Sep 2026 10:42', '412 KB'],
  ['R-0335', 'P-0091', 'S-2026-0341', 'meningioma', '27 Sep 2026 09:16', '398 KB'],
  ['R-0334', 'P-0127', 'S-2026-0340', 'notumor', '26 Sep 2026 16:04', '371 KB'],
  ['R-0333', 'P-0034', 'S-2026-0339', 'pituitary', '26 Sep 2026 14:28', '405 KB'],
  ['R-0332', 'P-0126', 'S-2026-0338', 'glioma', '26 Sep 2026 11:51', '417 KB'],
  ['R-0331', 'P-0126', 'S-2026-0301', 'glioma', '24 Sep 2026 15:09', '409 KB'],
  ['R-0330', 'P-0125', 'S-2026-0299', 'meningioma', '22 Sep 2026 10:30', '401 KB'],
].map(([id, patient, scanId, result, created, size]) => ({
  id, patient_id: patient, scan_id: scanId, result: result as TumorClass, created, size,
  blob_path: `neurolens-patients/${patient}/${scanId}/report.pdf`,
}));

export const SYSTEM: SystemInfo = {
  model: {
    name: 'Fibonacci-Net', source: 'Hugging Face Hub · neurolens/brain-tumor-classifier', revision: 'a1b2c3d (pinned)',
    parameters: '0.38 M · 4.6 MB', input: '224 × 224 RGB, pixels / 255', classes: 'glioma · meningioma · notumor · pituitary',
    explanation: 'Grad-CAM++', loaded: '27 Sep 2026, 08:00',
  },
  services: [
    { name: 'FastAPI backend', detail: 'Azure Container Apps', status: 'Healthy', healthy: true },
    { name: 'Model registry', detail: 'Hugging Face Hub', status: 'Connected', healthy: true },
    { name: 'Database', detail: 'MongoDB Atlas (M0)', status: 'Connected', healthy: true },
    { name: 'Vector index', detail: 'Atlas Vector Search', status: 'Ready', healthy: true },
    { name: 'File storage', detail: 'Azure Blob Storage', status: 'Connected', healthy: true },
  ],
  comparison: [
    { model: 'EfficientNetB0', track: 'A', config: 'S2', accuracy: 0.962, macro_f1: 0.958, glioma_recall: 0.931, params: '4.38 M', latency_ms: 41, selected: false },
    { model: 'Fibonacci-Net', track: 'B', config: 'lr=3e-4', accuracy: 0.955, macro_f1: 0.951, glioma_recall: 0.927, params: '0.38 M', latency_ms: 12, selected: true },
    { model: 'MobileNetV2', track: 'A', config: 'S2', accuracy: 0.947, macro_f1: 0.942, glioma_recall: 0.905, params: '2.59 M', latency_ms: 18, selected: false },
    { model: 'Xception', track: 'A', config: 'S2', accuracy: 0.944, macro_f1: 0.94, glioma_recall: 0.911, params: '21.39 M', latency_ms: 96, selected: false },
    { model: 'Custom CNN', track: 'B', config: 'tuned', accuracy: 0.912, macro_f1: 0.905, glioma_recall: 0.862, params: '1.21 M', latency_ms: 9, selected: false },
  ],
  comparison_is_placeholder: true,
};

/** Demo multi-slice study: three slices of one scan, one of which disagrees. */
export const STUDY: Study = {
  id: 'ST-2026-0007', patient_id: 'P-0128', date: '27 Sep 2026, 10:42', scan_date: '2026-09-27', sequence: 'T1-weighted, contrast-enhanced',
  prediction: 'glioma', confidence: 0.781, probabilities: probs(0.781, 0.172, 0.031, 0.016),
  slice_count: 3, slice_agreement: '2 / 3', status: 'Flagged', model_version: MODEL, report_path: '/api/studies/ST-2026-0007/report',
  explanation: 'Combined result of 3 slices: Glioma, with an average confidence of 78.1%. 2 of 3 slices predict Glioma; the others predict ' +
    'Meningioma. The slices disagree, so this study is flagged for careful review.',
  slices: [
    { ...SCAN_RESULT, id: 'S-2026-0343', study_id: 'ST-2026-0007', slice_index: 1 },
    { ...scan('S-2026-0344', 'P-0128', '27 Sep 2026, 10:42', 'glioma', 0.902, probs(0.902, 0.071, 0.017, 0.01), 'Awaiting review', '4 / 5'), study_id: 'ST-2026-0007', slice_index: 2 },
    { ...scan('S-2026-0345', 'P-0128', '27 Sep 2026, 10:42', 'meningioma', 0.596, probs(0.507, 0.596, 0.057, 0.032), 'Flagged', '2 / 5', { x: 0.55, y: 0.4, r: 0.08 }), study_id: 'ST-2026-0007', slice_index: 3 },
  ],
};
