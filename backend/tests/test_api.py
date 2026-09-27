"""Patients, scans, reports and dashboard API tests.

Uses an in-memory MongoDB (mongomock) and a fake model, so neither a database nor TensorFlow is needed.
Run from the backend folder:  pytest -q
"""
import io
import os
import sys

import mongomock
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789"
os.environ["SKIP_MODEL_LOAD"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

import routers.scans as scans_router  # noqa: E402
import utils.database as database  # noqa: E402
from app import app  # noqa: E402


def fake_classify(image):
    heatmap = Image.new("RGB", image.size, (255, 0, 0))
    return {"prediction": "malignant", "confidence": 0.82, "probabilities": {"benign": 0.18, "malignant": 0.82},
            "gradcam": heatmap, "inference_seconds": 0.12}


@pytest.fixture
def client(monkeypatch):
    database.set_client(mongomock.MongoClient())
    monkeypatch.setattr(scans_router, "classify", fake_classify)
    with TestClient(app) as c:
        token = c.post("/api/auth/register", json={"full_name": "Dr. Test", "email": "doc@example.com",
                                                   "password": "secret123"}).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def png_bytes():
    buf = io.BytesIO()
    Image.new("L", (300, 260), 128).save(buf, format="PNG")
    return buf.getvalue()


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


def test_similar_cases_not_available_yet(client):
    assert client.get("/api/scans/S-2026-0001/compare/REF-1").status_code == 501


def test_system_info(client):
    info = client.get("/api/system/model").json()
    assert info["model"]["classes"] == "Benign · Malignant"
