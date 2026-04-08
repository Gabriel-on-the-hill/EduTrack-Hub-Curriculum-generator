import os
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin_api import router
from src.api.auth import build_signature, reset_replay_cache


def _signed_headers(*, method: str, path: str, body: bytes = b"", nonce: str = "nonce-1") -> dict[str, str]:
    timestamp = str(int(time.time()))
    secret = os.environ["ADMIN_AUTH_SECRET"]
    signature = build_signature(secret, timestamp, nonce, method, path, body)
    return {
        "X-Admin-Timestamp": timestamp,
        "X-Admin-Nonce": nonce,
        "X-Admin-Signature": signature,
    }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    os.environ["ADMIN_AUTH_SECRET"] = "test-secret"
    os.environ["ADMIN_AUTH_MAX_SKEW_SECONDS"] = "300"
    reset_replay_cache()


def teardown_function() -> None:
    reset_replay_cache()


def test_admin_headers_accept_valid_request():
    client = _client()
    headers = _signed_headers(method="GET", path="/api/admin/pending_jobs")
    response = client.get("/api/admin/pending_jobs", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"jobs": []}


def test_admin_headers_reject_invalid_signature():
    client = _client()
    headers = _signed_headers(method="GET", path="/api/admin/pending_jobs")
    headers["X-Admin-Signature"] = "deadbeef"
    response = client.get("/api/admin/pending_jobs", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid admin auth signature"


def test_admin_headers_reject_replay():
    client = _client()
    headers = _signed_headers(method="GET", path="/api/admin/pending_jobs", nonce="shared-nonce")
    first = client.get("/api/admin/pending_jobs", headers=headers)
    second = client.get("/api/admin/pending_jobs", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json()["detail"] == "Replay detected for admin auth nonce"


def test_admin_headers_reject_stale_timestamp():
    client = _client()
    secret = os.environ["ADMIN_AUTH_SECRET"]
    timestamp = str(int(time.time()) - 301)
    signature = build_signature(secret, timestamp, "stale-nonce", "GET", "/api/admin/pending_jobs", b"")
    response = client.get(
        "/api/admin/pending_jobs",
        headers={
            "X-Admin-Timestamp": timestamp,
            "X-Admin-Nonce": "stale-nonce",
            "X-Admin-Signature": signature,
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Stale admin auth timestamp"
