<p align="center"><img src="frontend/public/logo.svg" width="96" alt="NeuroLens logo" /></p>

<h1 align="center">NeuroLens</h1>

<p align="center">Explainable, case-grounded brain tumor MRI classification — research notebooks, a FastAPI backend and an Angular dashboard.</p>

> Research prototype for the NUS-ISS PRS Practice Module — **not a diagnostic device**. Use synthetic or public-dataset images only.

NeuroLens classifies an MRI slice, shows **where the model looked** (Grad-CAM heatmap), finds the **most similar confirmed cases** (vector search), compares cases side by side, and produces a **report** — all from one dashboard with patient records and user accounts.

---

## 1. Open the live app

| | |
|---|---|
| **URL** | **https://neurolens-xai.azurewebsites.net** |
| **Administrator email** | `admin@neurolens.com` |
| **Administrator password** | `Neurolens@2026` |
| API documentation | https://neurolens-xai.azurewebsites.net/docs |
| Health check | https://neurolens-xai.azurewebsites.net/api/health — shows `"model":"ready"` when the app is ready |
| **Video presentation** | https://www.youtube.com/watch?v=DgXNyZJQaDQ |

> The first request after the site has been idle can take a minute while the container starts and the model loads.

Nothing needs to be installed: the app runs in the cloud, and the test images are in this repository.

## 2. What to try

Download or clone this repository to get the test images in [`test_data/`](test_data):

| Folder | Contents | Use it for |
|---|---|---|
| [`test_data/single_slice/`](test_data/single_slice) | 10 held-out test slices for each of the 4 classes (`glioma`, `meningioma`, `notumor`, `pituitary`) | a normal classification |
| [`test_data/multi_slice/`](test_data/multi_slice) | real slices of the same patient, one folder per patient (4–5 slices each) | the multi-slice upload |

1. **Log in** with the administrator account above.
2. **Patients → Add patient** (pseudonymised: age, sex, referring unit).
3. **New Classification** → choose the patient and upload **one** image from `test_data/single_slice/` → prediction, class probabilities and the Grad-CAM heatmap.
4. **Mark reviewed** on the result page — reviewed scans become confirmed cases for similar-case search.
5. **Find similar cases** → **Compare** with one of them: similarity, heatmap overlap, class agreement and the reasons.
6. **Multi-slice:** New Classification again, select **all** images in one patient folder of `test_data/multi_slice/` → one combined result, each slice with its own heatmap, flagged for review if the slices disagree.
7. **Download report** (Word) from a result page or from **Reports**.
8. **Model & System** shows the deployed model and service status; **Users** lets the administrator add team members.

## 3. Final deliverables

| Deliverable | Where | What it shows |
|---|---|---|
| **Research notebook** | [`research/BRAIN_TUMOR_CLASSIFICATION.ipynb`](research/BRAIN_TUMOR_CLASSIFICATION.ipynb) (Google Colab, GPU) | Data cleaning and preprocessing (Sections 1–4); fine-tuned MobileNetV2, EfficientNetB0 and Xception vs. a custom CNN and Fibonacci-Net trained from scratch, with KerasTuner and an ablation study (5–6); model selection with a fixed decision rule (7); comparison of 5 heatmap (CAM) methods (8); similar-case search evaluation (9); publishing the selected model (10) |
| **Result tables** | [`research/results.csv`](research/results.csv), [`final_comparison.csv`](research/final_comparison.csv), [`cam_comparison.csv`](research/cam_comparison.csv) | Every model configuration with accuracy, macro-F1, per-class recall, size and CPU latency; the heatmap-method comparison |
| **Trained model** | [Hugging Face: Bharathikannan/brain-tumor-classification](https://huggingface.co/Bharathikannan/brain-tumor-classification) | The selected model and its `model_info.json` (classes, metrics, chosen heatmap method) |
| **Web application** | https://neurolens-xai.azurewebsites.net · source in [`backend/`](backend) (FastAPI) and [`frontend/`](frontend) (Angular) | Classification with heatmaps, similar cases and comparison, multi-slice studies, reports, patient records and user accounts |
| **Test data** | [`test_data/`](test_data) | Held-out single slices and patient-grouped slices for trying the app |
| **Deployment** | [`Dockerfile`](Dockerfile), [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | One Docker image built, tested and deployed to Azure automatically |
| **Automated tests** | [`backend/tests/`](backend/tests) | 25 tests (accounts, patients, classification, similar cases, multi-slice, and a check that Grad-CAM never changes the model); the 24 that need no TensorFlow run before every deployment |
| **Video presentation** | https://www.youtube.com/watch?v=DgXNyZJQaDQ | 12-minute walkthrough: live demo, then models, explanations, similar cases and findings |

## 4. How it runs in the cloud

```
GitHub (push to main)
   └─ GitHub Actions: 24 tests → Docker build → Azure Container Registry → Azure Web App → check the live version
Azure Web App (one Docker container)
   ├─ Angular dashboard
   └─ FastAPI backend ── loads the model from Hugging Face at start-up
         ├─ MongoDB Atlas      patients, scans, users, embeddings + Atlas Vector Search
         └─ Azure Blob Storage  scan images and heatmaps (private, short-lived links)
```

- **Model updates** need no code change: upload the new model to Hugging Face, change the Web App setting `HF_REPO_ID` / `HF_MODEL_FILENAME`, and restart.
- **Settings and secrets** (database, storage, login keys) are Web App configuration — never stored in this repository.
- **Research prototype:** not a diagnostic device; all patient records are synthetic.

## 5. Data sources

**Main dataset (training, validation, testing):**

- Nickparvar, M. *Brain Tumor MRI Dataset*, **version 1**. Kaggle. https://www.kaggle.com/datasets/masoudnickparvar/brain-tumor-mri-dataset
  7,023 2D MRI slices (JPG) in 4 classes: glioma, meningioma, pituitary tumour, no tumour; split by the publisher into Training (5,712) and Testing (1,311). Version 1 keeps the natural class imbalance; version 2 (balanced by the publisher) is not used.

The Kaggle dataset combines three public collections:

| Collection | Reference |
|---|---|
| Figshare | Cheng, J. *brain tumor dataset*. figshare. https://doi.org/10.6084/m9.figshare.1512427 — described in Cheng, J., et al. (2015). Enhanced performance of brain tumor classification via tumor region augmentation and partition. *PLoS ONE*, 10(10), e0140381. |
| SARTAJ | Bhuvaji, S., et al. (2020). *Brain Tumor Classification (MRI)*. Kaggle. https://www.kaggle.com/datasets/sartajbhuvaji/brain-tumor-classification-mri |
| Br35H | Hamada, A. (2020). *Br35H :: Brain Tumor Detection 2020*. Kaggle. https://www.kaggle.com/datasets/ahmedhamada0/brain-tumor-detection |

**How the data is used:** duplicates and training copies of test images are removed (MD5), 15% of the training data is held out for validation, minority classes are oversampled on the training split only, and the Testing split is used once for the final comparison (see the notebook, Sections 2–3). `test_data/single_slice/` holds 40 images taken from the Testing split (10 per class, none identical to a training image).

**Multi-slice demo:** the original Figshare collection above (licence CC BY 4.0) includes a patient ID for each slice. `test_data/multi_slice/` holds 5 patients per tumour class (meningioma, glioma, pituitary), up to 5 slices each, converted from the original MATLAB files to JPG — upload all slices of one patient folder together. The collection has no "no tumour" class, and its slices are part of the Kaggle dataset (so very likely seen in training): use them to demonstrate the feature, not to measure accuracy.

**Licences:** each dataset is used under the terms on its own page, for research and education only, with attribution. No real patient data is stored in the app; all patient records are synthetic.

---

Developer guide (local setup, project structure, API reference): [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)
