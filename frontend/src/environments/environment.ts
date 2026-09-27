// Development settings (used by `ng serve`).
export const environment = {
  production: false,
  // FastAPI backend (backend/) — run it with `python app.py`
  apiUrl: 'http://localhost:8000/api',
  // false = every page calls the real backend (normal use)
  // true  = patient/scan/report pages show demo data from mock-data.ts (UI work without a backend);
  //         login and accounts always use the real backend
  useMockData: false,
};
