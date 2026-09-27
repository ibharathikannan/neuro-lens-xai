# NeuroLens

Explainable brain tumor MRI classification: research notebooks, a FastAPI backend (accounts, login, JWT authentication, model utilities) and an Angular admin dashboard.

```
code/
├── research/                 Colab notebooks
│   ├── BRAIN_TUMOR_CLASSIFICATION.ipynb   full model comparison and selection
│   └── BRAIN_TUMOR_STEP_BY_STEP.ipynb     data loading and preprocessing, step by step
├── backend/                  FastAPI
│   ├── app.py                entry point (CORS, routers, startup)
│   ├── routers/
│   │   ├── auth_routes.py    /api/auth/register · /login · /token · /me
│   │   └── routes.py         /api/health
│   ├── utils/
│   │   ├── config.py         settings from .env, image size and class names
│   │   ├── database.py       MongoDB connection + indexes
│   │   ├── security.py       bcrypt password hashing, JWT create/verify, get_current_user
│   │   ├── schemas.py        request/response models and validation
│   │   ├── logger.py
│   │   ├── model_architecture.py  Fibonacci-Net custom layers (identical to the notebook) + CUSTOM_OBJECTS
│   │   ├── processing.py     uploaded image -> (1, 224, 224, 3) in [0, 1], as in training
│   │   ├── gradcam.py        Grad-CAM heatmap (Fibonacci-Net and pretrained backbones) + overlay
│   │   └── report_generator.py  template-based brain MRI report (DOCX)
│   ├── tests/test_auth.py    auth tests (in-memory MongoDB, no database needed)
│   ├── requirements.txt
│   └── .env.example
└── frontend/                 Angular 22 dashboard
    └── src/app/
        ├── service.ts        ALL backend calls go through here
        ├── models.ts         API data types
        ├── mock-data.ts      demo data (used by service.ts only while useMockData = true)
        ├── auth.guard.ts     protects dashboard pages
        ├── layout/           sidebar + top bar
        ├── shared/           image and chip components
        └── pages/            login, register, dashboard, patients, patient-detail,
                              new-scan, result, similar, compare, reports, model-system
```

## 1. Research

Open the notebooks in Google Colab with a GPU runtime. `BRAIN_TUMOR_CLASSIFICATION.ipynb` trains and compares every model, saves results to Google Drive and exports the selected model for the backend.

## 2. Backend

Use **Python 3.10–3.12** — TensorFlow (needed for classification) is not available for newer versions.

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env
```

Edit `.env`:
- `MONGODB_URI` — your MongoDB Atlas connection string (or `mongodb://localhost:27017`)
- `JWT_SECRET_KEY` — a long random value: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

```bash
python app.py                    # http://localhost:8000  ·  API docs: http://localhost:8000/docs
pytest -q                        # run the auth tests
```

### Auth API

| Method | Route | Body | Returns |
|---|---|---|---|
| POST | `/api/auth/register` | `{ full_name, email, password }` | `201` token + user (the **first** account becomes `admin`) |
| POST | `/api/auth/login` | `{ email, password }` | token + user |
| POST | `/api/auth/token` | form: `username`, `password` | same — used by the **Authorize** button in `/docs` |
| GET | `/api/auth/me` | header `Authorization: Bearer <token>` | current user |
| GET | `/api/health` | — | `{ status, database }` |

Rules: passwords are hashed with bcrypt and need 8+ characters with a letter and a number; emails are stored in lower case and must be unique (`409` otherwise); login errors never reveal whether an email exists; tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60).

To protect a new route, add the dependency:

```python
from utils.security import get_current_user, require_admin

@router.get("/api/patients")
async def list_patients(user: dict = Depends(get_current_user)):   # any logged-in user
    ...

@router.delete("/api/patients/{id}")
async def delete_patient(id: str, user: dict = Depends(require_admin)):   # administrators only
    ...
```

### Utilities for the classification routes

```python
from utils.model_architecture import CUSTOM_OBJECTS
from utils.processing import preprocess_image
from utils.gradcam import find_last_conv_layer, make_gradcam_heatmap, overlay_heatmap
from utils.report_generator import generate_docx_report

model = tf.keras.models.load_model(path, custom_objects=CUSTOM_OBJECTS, compile=False)
x = preprocess_image(pil_image)                       # (1, 224, 224, 3)
probs = model.predict(x)[0]                           # order = CLASS_NAMES in utils/config.py
heatmap = make_gradcam_heatmap(x, model, find_last_conv_layer(model))
overlay = overlay_heatmap(pil_image, heatmap)         # PIL image for the dashboard / report
```

## 3. Frontend

```bash
cd frontend
npm install
npm start                        # http://localhost:4200
```

Settings are in `src/environments/environment.ts`:
- `apiUrl` — backend URL (default `http://localhost:8000/api`)
- `useMockData` — `true` shows demo data on the clinical pages (patients, scans, reports) until those backend routes exist. **Login, account creation and the current user always use the real backend.** Set it to `false` once the routes are implemented; the expected routes are listed at the top of `service.ts`.

`src/environments/environment.prod.ts` is used by `npm run build` — set its `apiUrl` to the deployed backend.

### How the frontend talks to the backend

- Pages never use `HttpClient` directly — they call methods on `ApiService` in **`service.ts`**.
- `service.ts` stores the JWT after login/registration, adds `Authorization: Bearer <token>` to every protected request, and logs the user out (back to `/login`) on a `401`.
- `auth.guard.ts` sends anyone without a valid, unexpired token to `/login` and returns them to the page they wanted after signing in.

## Notes

- Research prototype — use synthetic patient records only.
- Never commit `.env`. In Azure Container Apps, set the same variables as secrets.
- The backend's `CORS_ORIGINS` must include the dashboard's URL (e.g. the Azure Static Web Apps domain).

## 4. Deployment (GitHub Actions → Azure)

Live app: **https://neurolens-xai.azurewebsites.net** — one Docker image serves the dashboard and the API (`/api`, docs at `/docs`).

Every push to `main` runs `.github/workflows/deploy.yml`:

1. **Backend tests** (in-memory database, fake model).
2. **Build and push** `mlprojectdocker.azurecr.io/neurolens:latest` and `:<commit>` — the Angular dashboard is built inside the image.
3. **Deploy** — the registry webhook `neurolensxai` tells the Web App to pull the new `latest` image.
4. **Verify** — waits until `/api/health` on the live site reports the commit that was just built.

Repository secrets (Settings → Secrets and variables → Actions): `ACR_USERNAME`, `ACR_PASSWORD`.

Azure resources: Web App `neurolens-xai` (resource group `mlprojectdocker`, B1 plan `ASP-bharathikannanapigroup-9cca`). Runtime settings — `MONGODB_URI`, `JWT_SECRET_KEY`, `FIRST_ADMIN_*`, `HF_REPO_ID`, `HF_MODEL_FILENAME`, `CLASS_NAMES` — are set in the Web App's configuration, never in the image.

Build locally instead:

```bash
docker build -t mlprojectdocker.azurecr.io/neurolens:latest .
docker login mlprojectdocker.azurecr.io
docker push mlprojectdocker.azurecr.io/neurolens:latest
```

### Switching to the brain tumor model

Upload the exported model (and `model_info.json`) to Hugging Face, then update the Web App settings — no code change needed:

```bash
az webapp config appsettings set -g mlprojectdocker -n neurolens-xai --settings \
  HF_REPO_ID=<user>/<brain-tumor-repo> HF_MODEL_FILENAME=brain_tumor_model.keras \
  CLASS_NAMES=glioma,meningioma,notumor,pituitary MODEL_DISPLAY_NAME=Fibonacci-Net
```
