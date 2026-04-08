from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.security.request_signing import build_auth_headers, validate_signed_request


app = FastAPI()


@app.get("/secure", dependencies=[Depends(validate_signed_request)])
def secure_endpoint():
    return {"ok": True}


@app.get("/secure/health")
def health_endpoint():
    return {"status": "ok"}


client = TestClient(app)


def test_valid_signature(monkeypatch):
    monkeypatch.setenv("EDUTRACK_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("EDUTRACK_ALLOWED_SERVICES", "svc-a")

    headers = build_auth_headers("svc-a", "GET", "/secure")
    response = client.get("/secure", headers=headers)
    assert response.status_code == 200


def test_timestamp_skew_rejected(monkeypatch):
    monkeypatch.setenv("EDUTRACK_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("EDUTRACK_ALLOWED_SERVICES", "svc-a")
    monkeypatch.setenv("EDUTRACK_TIMESTAMP_SKEW_SECONDS", "1")

    headers = build_auth_headers("svc-a", "GET", "/secure")
    headers["X-Edutrack-Timestamp"] = "1"
    response = client.get("/secure", headers=headers)
    assert response.status_code == 401


def test_nonce_replay_rejected(monkeypatch):
    monkeypatch.setenv("EDUTRACK_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("EDUTRACK_ALLOWED_SERVICES", "svc-a")

    headers = build_auth_headers("svc-a", "GET", "/secure")
    first = client.get("/secure", headers=headers)
    second = client.get("/secure", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 403


def test_health_exempt():
    response = client.get("/secure/health")
    assert response.status_code == 200
