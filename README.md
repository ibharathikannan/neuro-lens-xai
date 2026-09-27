<p align="center"><img src="frontend/public/logo.svg" width="96" alt="NeuroLens logo" /></p>

<h1 align="center">NeuroLens</h1>

<p align="center">Explainable, case-grounded brain tumor MRI classification — research notebooks, a FastAPI backend and an Angular dashboard.</p>

> Research prototype for the NUS-ISS PRS Practice Module — **not a diagnostic device**. Use synthetic or public-dataset images only.

NeuroLens classifies an MRI slice, shows **where the model looked** (Grad-CAM heatmap), finds the **most similar confirmed cases** (vector search), compares cases side by side, and produces a **report** — all from one dashboard with patient records and user accounts.

---

## 1. Use the live app (Azure)

| | |
|---|---|
| **URL** | **https://neurolens-xai.azurewebsites.net** |
| API docs | https://neurolens-xai.azurewebsites.net/docs |
| Health check | https://neurolens-xai.azurewebsites.net/api/health |
| Administrator email | `admin@example.com` |
| Administrator password | not stored in this repository — see below |

The administrator password is the `FIRST_ADMIN_PASSWORD` setting of the Web App. Anyone with access to the Azure subscription can read it:

```bash
az webapp config appsettings list -g mlprojectdocker -n neurolens-xai --query "[?name=='FIRST_ADMIN_PASSWORD'].value" -o tsv
```

(or Azure Portal → App Services → `neurolens-xai` → Settings → Environment variables).

**Other users:** self-registration is switched off on the live site. The administrator adds team members on the **Users** page (left menu), and everyone can change their password under **My Account** (click your name in the top bar).

> The first request after the site has been idle can take a minute while the container and model start.

---

## 2. Run it on your computer

### What you need

| Tool | Version | Check |
|---|---|---|
| Python | **3.10 – 3.12** (TensorFlow does not support 3.13+ yet) | `py -0` (Windows) · `python3 --version` |
| Node.js | 20 or newer (tested with 24) | `node -v` |
| Git | any | `git --version` |

No Python 3.12 yet? On Windows run `py install 3.12` (Python install manager) or get the installer from [python.org](https://www.python.org/downloads/) (tick *Add python.exe to PATH*).

### Step 1 — Get the code

```bash
git clone https://github.com/ibharathikannan/neuro-lens-xai.git
cd neuro-lens-xai
```

### Step 2 — Backend environment (one time)

Windows (PowerShell or Command Prompt):

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
copy .env.example .env
```

macOS / Linux:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
```

The install downloads TensorFlow (about 1.8 GB on disk), so it takes a few minutes.

> PowerShell says *running scripts is disabled*? Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt.

### Step 3 — Settings (`backend/.env`)

Open `backend/.env` and fill in at least:

| Setting | What to put |
|---|---|
| `MONGODB_URI` | your MongoDB Atlas connection string (`mongodb+srv://…`) or `mongodb://localhost:27017` for a local MongoDB |
| `MONGODB_DB_NAME` | e.g. `neurolens_dev` — use a **different name from the live site** to keep local test data separate |
| `JWT_SECRET_KEY` | a long random value: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` | the administrator account created on first start (this is how you log in) |
| `AZURE_STORAGE_CONNECTION_STRING` | optional — leave empty to keep images inside MongoDB |

The model settings (`HF_REPO_ID`, `HF_MODEL_FILENAME`, `CLASS_NAMES`) already point to the published Hugging Face model; the model downloads automatically on the first start. All settings are explained in `.env.example`.

### Step 4 — Start the backend

With the virtual environment active, from `backend/`:

```bash
python app.py
```

- API: http://localhost:8000 · interactive docs: http://localhost:8000/docs
- The model loads in the background (about 10–30 s the first time). It is ready when http://localhost:8000/api/health shows `"model":"ready"`.

### Step 5 — Start the dashboard

In a **second terminal**, from the repository folder:

```bash
cd frontend
npm install
npm start
```

Open **http://localhost:4200** and sign in with `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` from your `.env`.
(With `ALLOW_REGISTRATION=true` you can also create an account on the sign-up page — the very first account becomes the administrator.)

### Step 6 — Try it

1. **Patients → Add patient** (pseudonymised: age, sex, unit).
2. **New Classification** → choose the patient, upload an MRI image → prediction, confidence and heatmap.
3. **Mark reviewed** on the result page — reviewed scans become confirmed cases for similar-case search.
4. **Find similar cases** → **Compare** with one of them.
5. **Download report** (DOCX) from the result page or **Reports**.

### Next time

```bash
cd backend
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
python app.py
```

and in a second terminal `cd frontend` → `npm start`.

### Optional: one server, like the deployed app

The Docker image serves the built dashboard from the backend. To do the same locally:

```bash
cd frontend
npm run build
cd ../backend
$env:STATIC_DIR="../frontend/dist/neurolens-dashboard/browser"    # Command Prompt: set STATIC_DIR=...  ·  macOS/Linux: export STATIC_DIR=...
python app.py                                                   # dashboard + API on http://localhost:8000
```

### Run the tests

```bash
cd backend
pytest -q          # 19 tests — in-memory database and a fake model, no internet or MongoDB needed
```

### Troubleshooting

| Problem | Fix |
|---|---|
| `No matching distribution found for tensorflow-cpu` | Python is too new — create the environment with Python 3.12 (`py -3.12 -m venv .venv`). |
| `No runtime installed that matches 3.12` | Install it: `py install 3.12`, or use the python.org installer. |
| Dashboard says *Cannot reach the server* | The backend is not running on port 8000 — start it (Step 4). |
| *Model is not available yet* when classifying | Wait until `/api/health` shows `"model":"ready"`; check the backend terminal for download errors. |
| Login fails with the admin email | The admin is only created when that email does not exist yet. Use the password it was first created with, or a different `MONGODB_DB_NAME`. |
| `Address already in use` | Another copy is running — close it, or run `uvicorn app:app --port 8001` and change `apiUrl` in `frontend/src/environments/environment.ts`. |

---

## 3. Project structure

```
neuro-lens-xai/
├── research/                 Colab notebooks
│   ├── BRAIN_TUMOR_CLASSIFICATION.ipynb   model comparison and selection, CAM methods, similar-case search, publishing
│   └── BRAIN_TUMOR_STEP_BY_STEP.ipynb     data loading and preprocessing, step by step
├── backend/                  FastAPI
│   ├── app.py                entry point (CORS, routers, startup, serves the built dashboard)
│   ├── routers/
│   │   ├── auth_routes.py    /api/auth: register · login · token · me · settings · change-password · users (admin)
│   │   ├── patients.py       /api/patients
│   │   ├── scans.py          /api/scans: classify · review · report · similar · compare
│   │   ├── dashboard.py      /api/dashboard/summary · /api/reports · /api/system/model
│   │   └── routes.py         /api/health
│   ├── scripts/
│   │   └── load_reference_library.py   loads labelled images for similar-case search
│   ├── utils/
│   │   ├── config.py         settings from .env, image size and class names
│   │   ├── database.py       MongoDB connection + indexes
│   │   ├── security.py       bcrypt password hashing, JWT create/verify, get_current_user
│   │   ├── schemas.py        request/response models and validation
│   │   ├── model_service.py  model download (Hugging Face), prediction, embedding, heatmap
│   │   ├── model_architecture.py  Fibonacci-Net custom layers (identical to the notebook)
│   │   ├── processing.py     uploaded image -> (1, 224, 224, 3) in [0, 1], as in training
│   │   ├── gradcam.py        Grad-CAM heatmap + overlay
│   │   ├── similarity.py     similar-case search (Atlas Vector Search / exact) and case comparison
│   │   ├── blob_storage.py   scan images in Azure Blob Storage, read-only links (SAS)
│   │   ├── report_generator.py  template-based MRI report (DOCX)
│   │   └── views.py, logger.py
│   ├── tests/                API tests (in-memory MongoDB and a fake model)
│   ├── requirements.txt      runtime packages · requirements-dev.txt adds the test tools
│   └── .env.example
├── frontend/                 Angular 22 dashboard
│   ├── public/               logo.svg, favicon
│   └── src/app/
│       ├── service.ts        ALL backend calls go through here
│       ├── models.ts         API data types
│       ├── auth.guard.ts     login / administrator guards
│       ├── layout/           sidebar + top bar
│       ├── shared/           image and chip components
│       └── pages/            login, register, dashboard, patients, patient-detail, new-scan, result,
│                             similar, compare, reports, model-system, account, users
├── Dockerfile                one image: dashboard + API + model
└── .github/workflows/deploy.yml   tests → build → push → deploy → verify
```

---

## 4. How it works

### Accounts and security

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/auth/register` | create an account (only while `ALLOW_REGISTRATION=true`; the first account becomes `admin`) |
| POST | `/api/auth/login` | email + password → JWT |
| GET | `/api/auth/me` | current user |
| GET | `/api/auth/settings` | whether self-registration is open (public) |
| POST | `/api/auth/change-password` | new password; sessions using the old one are signed out |
| GET / POST | `/api/auth/users` | administrators list and add team members |
| PATCH | `/api/auth/users/{id}` | administrators change a role or disable an account |

Passwords are hashed with bcrypt (8+ characters with a letter and a number); emails are unique and stored in lower case; login errors never reveal whether an email exists; tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60). Every clinical route requires a valid token.

### Classification and explanation

`POST /api/scans/classify` preprocesses the image exactly as in training, runs the model downloaded from Hugging Face, builds the Grad-CAM heatmap and stores the result with the patient. The choice of explanation method is justified in Section 8 of `BRAIN_TUMOR_CLASSIFICATION.ipynb`.

### Similar-case search

Each classified scan stores an **embedding** — the feature vector the model's final layer receives, scaled to unit length — plus a small copy of its heatmap. `GET /api/scans/{id}/similar` returns the nearest **confirmed** cases by cosine similarity; `GET /api/scans/{id}/compare/{caseId}` compares two cases (embedding similarity, heatmap overlap, focus region, class agreement, template-based reasons).

Confirmed cases are the **reference library** (labelled dataset images) and **patient scans marked as reviewed**. Search uses **MongoDB Atlas Vector Search** (index `embedding_index`, created automatically) and falls back to an exact search inside the API when Atlas search is unavailable. Only embeddings from the currently deployed model are compared.

Load the reference library from `backend/` (virtual environment active, same `.env` as the app) using the **training** images, never the test set:

```bash
python scripts/load_reference_library.py --data-dir "<dataset>/Training" --per-class 250 --source "Kaggle Brain Tumor MRI v1 (training split)"
```

### Research notebooks

Open them in Google Colab with a GPU runtime. `BRAIN_TUMOR_CLASSIFICATION.ipynb` trains and compares every model (Sections 1–7), chooses the explanation method (8), evaluates similar-case search and chooses `k` (9), and publishes the selected model to Hugging Face with the exact settings for the app (10).

---
