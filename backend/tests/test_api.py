"""Patients, scans, reports and dashboard API tests.

Uses an in-memory MongoDB (mongomock) and a fake model, so neither a database nor TensorFlow is needed.
Run from the backend folder:  pytest -q
"""
import io
import os
import sys

import mongomock
import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789"
os.environ["SKIP_MODEL_LOAD"] = "true"
# Ignore the local .env: no Blob Storage, no seeded administrator, registration open, fixed classes and k
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""
os.environ["FIRST_ADMIN_EMAIL"] = ""
os.environ["ALLOW_REGISTRATION"] = "true"
os.environ["CLASS_NAMES"] = "benign,malignant"      # the tests use a two-class stand-in model
os.environ["SIMILAR_K"] = "5"

from fastapi.testclient import TestClient  # noqa: E402

import routers.scans as scans_router  # noqa: E402
import utils.database as database  # noqa: E402
from app import app  # noqa: E402


def fake_classify(image):
    """Stands in for the model: the embedding and prediction follow the image's grey level,
    so scans made from similar grey levels are similar cases."""
    grey = float(np.asarray(image.convert("L")).mean()) / 255
    vector = np.array([grey, 1 - grey, 0.3])
    heatmap = np.zeros((7, 7))
    heatmap[1:3, 4:6] = 1.0                           # focus in the upper right
    malignant = 0.3 + 0.6 * grey
    prediction = "malignant" if malignant >= 0.5 else "benign"
    return {"prediction": prediction, "confidence": max(malignant, 1 - malignant),
            "probabilities": {"benign": 1 - malignant, "malignant": malignant},
            "gradcam": Image.new("RGB", image.size, (255, 0, 0)), "heatmap": heatmap,
            "embedding": (vector / np.linalg.norm(vector)).tolist(), "inference_seconds": 0.12}


@pytest.fixture
def client(monkeypatch):
    database.set_client(mongomock.MongoClient())
    monkeypatch.setattr(scans_router, "classify", fake_classify)
    with TestClient(app) as c:
        token = c.post("/api/auth/register", json={"full_name": "Dr. Test", "email": "doc@example.com",
                                                   "password": "secret123"}).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def png_bytes(grey=200):
    buf = io.BytesIO()
    Image.new("L", (300, 260), grey).save(buf, format="PNG")
    return buf.getvalue()


def classify(client, patient_id="P-0001", grey=200):
    r = client.post("/api/scans/classify", data={"patient_id": patient_id},
                    files={"file": ("scan.png", png_bytes(grey), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()


def test_everything_requires_login(client):
    anon = TestClient(app)
    for path in ["/api/patients", "/api/dashboard/summary", "/api/reports", "/api/system/model", "/api/scans/S-2026-0001"]:
        assert anon.get(path).status_code == 401, path


def test_patient_and_scan_flow(client):
    p = client.post("/api/patients", json={"age": 54, "sex": "F", "referring_unit": "Clinic B", "notes": "test"})
    assert p.status_code == 201 and p.json()["id"] == "P-0001"
    assert client.post("/api/patients", json={"age": 200, "sex": "X"}).status_code == 422

    r = client.post("/api/scans/classify", data={"patient_id": "P-0001", "scan_date": "2026-09-27", "sequence": "T1", "notes": ""},
                    files={"file": ("scan.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    scan = r.json()
    assert scan["id"].startswith("S-") and scan["prediction"] == "malignant"
    assert scan["image_url"].startswith("data:image/jpeg;base64,") and scan["gradcam_url"]
    assert scan["status"] == "Awaiting review"

    assert client.get(f"/api/scans/{scan['id']}").json()["prediction"] == "malignant"
    assert client.post(f"/api/scans/{scan['id']}/review").json()["status"] == "Reviewed"

    detail = client.get("/api/patients/P-0001").json()
    assert detail["scans"] == 1 and detail["history"][0]["id"] == scan["id"] and detail["last_result"] == "malignant"
    assert client.get("/api/patients", params={"search": "0001"}).json()[0]["id"] == "P-0001"
    assert client.get("/api/patients", params={"search": "9999"}).json() == []

    report = client.get(f"/api/scans/{scan['id']}/report")
    assert report.status_code == 200 and report.content[:2] == b"PK"          # DOCX = zip

    summary = client.get("/api/dashboard/summary").json()
    assert summary["patients"] == 1 and summary["scans"] == 1 and summary["distribution"]["malignant"] == 100
    assert client.get("/api/reports").json()[0]["scan_id"] == scan["id"]


def test_classify_rejects_bad_input(client):
    client.post("/api/patients", json={"age": 40, "sex": "M"})
    bad = client.post("/api/scans/classify", data={"patient_id": "P-0001"}, files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 400
    missing = client.post("/api/scans/classify", data={"patient_id": "P-9999"}, files={"file": ("x.png", png_bytes(), "image/png")})
    assert missing.status_code == 404


def test_similar_cases_and_comparison(client):
    client.post("/api/patients", json={"age": 61, "sex": "M"})
    query = classify(client, grey=200)
    assert query["similar_agreement"] is None                       # nothing confirmed yet
    assert client.get(f"/api/scans/{query['id']}/similar").json()["cases"] == []

    close, far = classify(client, grey=195), classify(client, grey=20)
    unreviewed = classify(client, grey=201)                          # not reviewed -> not in the search space
    for s in (close, far):
        client.post(f"/api/scans/{s['id']}/review")

    # A confirmed case from the reference library, with the same embedding as the query
    ref = fake_classify(Image.new("L", (64, 64), 200))
    database.get_reference_collection().insert_one({
        "id": "REF-00001", "label": "malignant", "source_dataset": "Test dataset", "prediction": "malignant",
        "confidence": ref["confidence"], "probabilities": ref["probabilities"], "embedding": ref["embedding"],
        "embedding_model": scans_router.embedding_key(), "heatmap": [[0.0] * 7] * 7, "image_jpeg": None})

    result = client.get(f"/api/scans/{query['id']}/similar", params={"k": 5}).json()
    ids = [c["case_id"] for c in result["cases"]]
    assert ids[0] == "REF-00001" and ids[1] == close["id"] and ids[-1] == far["id"]
    assert query["id"] not in ids and unreviewed["id"] not in ids
    assert result["search_space"] == "1 reference cases + 2 reviewed patient scans"
    assert result["agreement"] == "2 / 3" and "exact search" in result["method"]
    assert result["cases"][0]["similarity"] == 100.0 and result["cases"][1]["source"] == "patient"

    # New scans get the case evidence in their explanation
    later = classify(client, grey=199)
    assert later["similar_agreement"] == "2 / 3" and "most similar confirmed cases" in later["explanation"]

    cmp = client.get(f"/api/scans/{query['id']}/compare/{close['id']}").json()
    assert cmp["same_class"] is True and cmp["heatmap_iou"] == 1.0 and cmp["focus_region"] == "Upper right"
    assert cmp["focus_distance_px"] == 0 and cmp["lesion_extent"] == "similar"
    assert cmp["reference"]["source_dataset"] == "reviewed NeuroLens scan" and len(cmp["explanation"]) == 4

    other = client.get(f"/api/scans/{query['id']}/compare/{far['id']}").json()
    assert other["same_class"] is False and other["similarity"] < cmp["similarity"]
    assert any("classes differ" in line for line in other["explanation"])

    ref_cmp = client.get(f"/api/scans/{query['id']}/compare/REF-00001").json()
    assert ref_cmp["focus_region"] == "Upper right" and ref_cmp["lesion_extent"] == "not comparable"
    assert ref_cmp["reference"]["source_dataset"] == "Test dataset"
    assert client.get(f"/api/scans/{query['id']}/compare/REF-99999").status_code == 404


def test_old_scans_are_analysed_on_demand(client):
    client.post("/api/patients", json={"age": 50, "sex": "F"})
    scan = classify(client)
    database.get_scans_collection().update_one({"id": scan["id"]}, {"$unset": {"embedding": "", "embedding_model": ""}})
    assert client.get(f"/api/scans/{scan['id']}/similar").status_code == 200
    stored = database.get_scans_collection().find_one({"id": scan["id"]})
    assert stored["embedding"] and stored["embedding_model"] == scans_router.embedding_key()


def test_similarity_helpers():
    from utils import similarity
    grid = [[0.0] * 28 for _ in range(28)]
    for y in range(20, 26):
        for x in range(2, 8):
            grid[y][x] = 1.0
    heat = similarity.compare_heatmaps(grid, grid)
    assert heat == {"iou": 1.0, "region": "Lower left", "distance": 0, "extent": "similar"}
    assert similarity.compare_heatmaps([[0.0]], grid)["region"] == "No clear focus"
    assert len(similarity.heatmap_grid(np.random.rand(7, 7))) == similarity.HEATMAP_GRID


def test_system_info(client):
    info = client.get("/api/system/model").json()
    assert info["model"]["classes"] == "Benign · Malignant"


def test_system_info_shows_model_comparison(client, tmp_path, monkeypatch):
    import routers.dashboard as dashboard
    csv_file = tmp_path / "final_comparison.csv"
    csv_file.write_text("\n".join([
        "model,track,config,test_accuracy,test_macro_f1,recall_glioma,params_M,size_MB,cpu_latency_ms",
        "MobileNetV2,A,S2,0.9458,0.9432,0.9067,2.587,23.1,229.8",
        "Fibonacci-Net,B,lr=0.001,0.9718,0.9709,0.9633,0.381,4.8,91.6",
    ]))
    monkeypatch.setattr(dashboard, "COMPARISON_CSV", str(csv_file))
    monkeypatch.setattr(dashboard, "MODEL_DISPLAY_NAME", "Fibonacci-Net (lr=0.001)")
    info = client.get("/api/system/model").json()
    assert info["comparison_is_placeholder"] is False
    first, second = info["comparison"]
    assert first["model"] == "Fibonacci-Net" and first["selected"] is True and first["params"] == "0.38 M"
    assert first["macro_f1"] == 0.9709 and first["latency_ms"] == 92 and second["selected"] is False

    monkeypatch.setattr(dashboard, "COMPARISON_CSV", str(tmp_path / "missing.csv"))
    empty = client.get("/api/system/model").json()
    assert empty["comparison"] == [] and empty["comparison_is_placeholder"] is True


# --- Multi-slice studies ---

def classify_study(client, greys, patient_id="P-0001"):
    files = [("files", (f"slice{i}.png", png_bytes(g), "image/png")) for i, g in enumerate(greys, 1)]
    return client.post("/api/studies/classify", data={"patient_id": patient_id, "sequence": "T1"}, files=files)


def test_study_combines_agreeing_slices(client):
    client.post("/api/patients", json={"age": 58, "sex": "M"})
    r = classify_study(client, [200, 198, 196])
    assert r.status_code == 201, r.text
    study = r.json()
    assert study["id"].startswith("ST-") and study["slice_count"] == 3
    assert study["prediction"] == "malignant" and study["slice_agreement"] == "3 / 3"
    assert study["status"] == "Awaiting review" and "All 3 slices" in study["explanation"]
    assert abs(sum(study["probabilities"].values()) - 1) < 1e-6
    assert [s["slice_index"] for s in study["slices"]] == [1, 2, 3]

    # every slice is a normal scan linked to the study
    one = client.get(f"/api/scans/{study['slices'][0]['id']}").json()
    assert one["study_id"] == study["id"] and one["image_url"]
    assert client.get(f"/api/studies/{study['id']}").json()["slice_agreement"] == "3 / 3"

    report = client.get(f"/api/studies/{study['id']}/report")
    assert report.status_code == 200 and report.content[:2] == b"PK"


def test_study_flags_disagreeing_slices_and_review_confirms_all(client):
    client.post("/api/patients", json={"age": 47, "sex": "F"})
    study = classify_study(client, [200, 195, 20]).json()          # malignant, malignant, benign
    assert study["prediction"] == "malignant" and study["slice_agreement"] == "2 / 3"
    assert study["status"] == "Flagged" and "disagree" in study["explanation"]

    reviewed = client.post(f"/api/studies/{study['id']}/review").json()
    assert reviewed["status"] == "Reviewed"
    for s in database.get_scans_collection().find({"study_id": study["id"]}):
        assert s["status"] == "Reviewed" and s["label"] == "malignant"   # one scan, one confirmed class


def test_study_rejects_bad_requests(client):
    client.post("/api/patients", json={"age": 40, "sex": "M"})
    assert classify_study(client, [200]).status_code == 400                 # fewer than 2 slices
    assert classify_study(client, [200] * 11).status_code == 400            # more than 10 slices
    assert classify_study(client, [200, 190], patient_id="P-9999").status_code == 404
    files = [("files", ("a.png", png_bytes(200), "image/png")), ("files", ("b.png", b"not an image", "image/png"))]
    bad = client.post("/api/studies/classify", data={"patient_id": "P-0001"}, files=files)
    assert bad.status_code == 400 and "b.png" in bad.json()["detail"]
    assert database.get_scans_collection().count_documents({}) == 0       # nothing stored when a file is invalid
    assert client.get("/api/studies/ST-2026-9999").status_code == 404


def test_combine_slices():
    from utils.studies import combine_slices
    slices = [{"prediction": "a", "probabilities": {"a": 0.9, "b": 0.1}},
              {"prediction": "b", "probabilities": {"a": 0.4, "b": 0.6}}]
    out = combine_slices(slices)
    assert out["prediction"] == "a" and abs(out["confidence"] - 0.65) < 1e-9
    assert out["slice_agreement"] == "1 / 2" and out["status"] == "Flagged"
