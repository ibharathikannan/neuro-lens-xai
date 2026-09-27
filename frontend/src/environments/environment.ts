// Development settings (used by `ng serve`).
export const environment = {
  production: false,
  // FastAPI backend (code/backend) — run it with `python app.py`
  apiUrl: 'http://localhost:8000/api',
  // true  = patient/scan/report pages use demo data from mock-data.ts until those backend routes exist
  // false = every page calls the real backend
  // Login, account creation and the current user ALWAYS use the real backend.
  useMockData: true,
};
