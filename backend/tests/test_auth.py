"""Auth API tests. They use an in-memory MongoDB (mongomock), so no database is needed.

Run from the backend folder:  pytest -q
"""
import os
import sys

import mongomock
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789"
os.environ["SKIP_MODEL_LOAD"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

import utils.database as database  # noqa: E402
from app import app  # noqa: E402

USER = {"full_name": "Dr. Test", "email": "Test.User@Example.com", "password": "secret123"}


@pytest.fixture
def client():
    database.set_client(mongomock.MongoClient())
    with TestClient(app) as c:
        yield c


def register(client, **overrides):
    return client.post("/api/auth/register", json={**USER, **overrides})


def test_register_returns_token_and_first_user_is_admin(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"] and body["token_type"] == "bearer"
    assert body["user"]["email"] == "test.user@example.com"        # stored lower-case
    assert body["user"]["role"] == "admin"
    assert "password" not in str(body["user"]).lower()

    second = register(client, email="second@example.com").json()
    assert second["user"]["role"] == "clinician"


def test_duplicate_email_is_rejected(client):
    register(client)
    r = register(client, email="TEST.user@example.com")
    assert r.status_code == 409


def test_weak_password_and_bad_email_are_rejected(client):
    assert register(client, password="short1").status_code == 422
    assert register(client, password="lettersonly").status_code == 422
    assert register(client, email="not-an-email").status_code == 422


def test_login_success_and_failure(client):
    register(client)
    ok = client.post("/api/auth/login", json={"email": USER["email"], "password": USER["password"]})
    assert ok.status_code == 200 and ok.json()["user"]["last_login"] is not None

    wrong = client.post("/api/auth/login", json={"email": USER["email"], "password": "wrong-pass1"})
    missing = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["detail"] == missing.json()["detail"]      # no hint which emails exist


def test_me_requires_a_valid_token(client):
    token = register(client).json()["access_token"]
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["full_name"] == "Dr. Test"


def test_expired_token_is_rejected(client, monkeypatch):
    import utils.security as security
    monkeypatch.setattr(security, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    user = {"_id": "0123456789abcdef01234567", "email": "x@example.com", "role": "clinician"}
    token = security.create_access_token(user)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and r.json()["detail"] == "Token has expired"


def test_swagger_form_login(client):
    register(client)
    r = client.post("/api/auth/token", data={"username": USER["email"], "password": USER["password"]})
    assert r.status_code == 200 and r.json()["access_token"]


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_first_admin_is_seeded(monkeypatch):
    import utils.security as security
    database.set_client(mongomock.MongoClient())
    monkeypatch.setattr(security, "FIRST_ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setattr(security, "FIRST_ADMIN_PASSWORD", "seeded-pass-1")
    monkeypatch.setattr(security, "FIRST_ADMIN_NAME", "Boss")
    security.seed_first_admin()
    security.seed_first_admin()                                         # second call does nothing
    assert database.get_users_collection().count_documents({}) == 1
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"email": "boss@example.com", "password": "seeded-pass-1"})
        assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
