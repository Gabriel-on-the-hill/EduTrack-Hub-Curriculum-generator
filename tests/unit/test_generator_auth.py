from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from src.api.generator_auth import SignedHeaderAuth, build_generator_auth_dependency


SECRET = "top-secret"
SERVICE = "generator-client"
FIXED_NOW = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)


def _sign(timestamp: str, nonce: str, body: bytes) -> str:
    canonical = "\n".join([
        SERVICE,
        timestamp,
        nonce,
        hashlib.sha256(body).hexdigest(),
    ])
    return hmac.new(SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _build_app() -> TestClient:
    auth = SignedHeaderAuth(
        secrets={SERVICE: SECRET},
        max_timestamp_skew_seconds=300,
        now_provider=lambda: FIXED_NOW,
    )
    app = FastAPI()

    @app.post("/api/generator/render")
    async def render(request: Request, _: None = Depends(build_generator_auth_dependency(auth))):
        return {
            "ok": True,
            "service": request.state.edutrack_service,
            "nonce": request.state.edutrack_nonce,
        }

    return TestClient(app)


def test_signed_headers_pass_validation() -> None:
    client = _build_app()
    body = b'{"prompt":"hello"}'
    timestamp = FIXED_NOW.isoformat().replace("+00:00", "Z")
    nonce = "nonce-12345"

    response = client.post(
        "/api/generator/render",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Edutrack-Service": SERVICE,
            "X-Edutrack-Timestamp": timestamp,
            "X-Edutrack-Nonce": nonce,
            "X-Edutrack-Signature": _sign(timestamp, nonce, body),
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "service": SERVICE, "nonce": nonce}


def test_missing_signed_headers_return_401() -> None:
    client = _build_app()

    response = client.post("/api/generator/render", json={"prompt": "hello"})

    assert response.status_code == 401


def test_invalid_signature_returns_401() -> None:
    client = _build_app()
    body = b'{"prompt":"hello"}'
    timestamp = FIXED_NOW.isoformat().replace("+00:00", "Z")

    response = client.post(
        "/api/generator/render",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Edutrack-Service": SERVICE,
            "X-Edutrack-Timestamp": timestamp,
            "X-Edutrack-Nonce": "nonce-12345",
            "X-Edutrack-Signature": "sha256=" + ("0" * 64),
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid request signature"


def test_timestamp_skew_returns_401() -> None:
    client = _build_app()
    body = b'{"prompt":"hello"}'
    timestamp = (FIXED_NOW - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    nonce = "nonce-12345"

    response = client.post(
        "/api/generator/render",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Edutrack-Service": SERVICE,
            "X-Edutrack-Timestamp": timestamp,
            "X-Edutrack-Nonce": nonce,
            "X-Edutrack-Signature": _sign(timestamp, nonce, body),
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Request timestamp outside allowed skew"


def test_nonce_replay_returns_403() -> None:
    client = _build_app()
    body = b'{"prompt":"hello"}'
    timestamp = FIXED_NOW.isoformat().replace("+00:00", "Z")
    nonce = "nonce-12345"
    headers = {
        "content-type": "application/json",
        "X-Edutrack-Service": SERVICE,
        "X-Edutrack-Timestamp": timestamp,
        "X-Edutrack-Nonce": nonce,
        "X-Edutrack-Signature": _sign(timestamp, nonce, body),
    }

    first = client.post("/api/generator/render", content=body, headers=headers)
    second = client.post("/api/generator/render", content=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 403
    assert second.json()["detail"] == "Replay detected"


def test_unknown_service_returns_403() -> None:
    client = _build_app()
    body = b'{"prompt":"hello"}'
    timestamp = FIXED_NOW.isoformat().replace("+00:00", "Z")
    nonce = "nonce-67890"
    canonical = "\n".join([
        "unknown-service",
        timestamp,
        nonce,
        hashlib.sha256(body).hexdigest(),
    ])
    signature = hmac.new(SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    response = client.post(
        "/api/generator/render",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Edutrack-Service": "unknown-service",
            "X-Edutrack-Timestamp": timestamp,
            "X-Edutrack-Nonce": nonce,
            "X-Edutrack-Signature": signature,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Unknown calling service"
