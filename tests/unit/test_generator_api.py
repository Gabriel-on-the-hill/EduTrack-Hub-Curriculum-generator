import hashlib
import hmac
import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.generator_api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _expected_signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    body: str,
) -> str:
    signing_payload = "\n".join([method.upper(), path, timestamp, body])
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_payload.encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


def test_create_generator_job_proxies_with_signature(monkeypatch):
    monkeypatch.setenv("GENERATOR_BASE_URL", "https://generator.internal")
    monkeypatch.setenv("GENERATOR_SHARED_SECRET", "super-secret")

    captured = {}

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"job_id": "job-123", "status": "queued"}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse()

    with patch("src.api.generator_api.requests.request", side_effect=fake_request):
        response = client.post(
            "/api/generator/jobs",
            json={"prompt": "Generate a worksheet", "options": {"grade": "5"}},
        )

    assert response.status_code == 200
    assert response.json() == {"job_id": "job-123", "status": "queued"}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://generator.internal/v1/generate"
    assert captured["json"] == {"prompt": "Generate a worksheet", "options": {"grade": "5"}}
    assert captured["timeout"] == 30

    timestamp = captured["headers"]["X-Edutrack-Timestamp"]
    expected_body = json.dumps(captured["json"], separators=(",", ":"), sort_keys=True)
    assert captured["headers"]["X-Edutrack-Signature"] == _expected_signature(
        "super-secret",
        "POST",
        "/v1/generate",
        timestamp,
        expected_body,
    )


def test_get_generator_job_proxies_with_signature(monkeypatch):
    monkeypatch.setenv("GENERATOR_BASE_URL", "https://generator.internal/")
    monkeypatch.setenv("GENERATOR_SHARED_SECRET", "another-secret")

    captured = {}

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"job_id": "job-123", "status": "completed"}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse()

    with patch("src.api.generator_api.requests.request", side_effect=fake_request):
        response = client.get("/api/generator/jobs/job-123")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert captured["method"] == "GET"
    assert captured["url"] == "https://generator.internal/v1/jobs/job-123"
    assert captured["json"] is None

    timestamp = captured["headers"]["X-Edutrack-Timestamp"]
    assert captured["headers"]["X-Edutrack-Signature"] == _expected_signature(
        "another-secret",
        "GET",
        "/v1/jobs/job-123",
        timestamp,
        "",
    )


def test_generator_proxy_requires_configuration(monkeypatch):
    monkeypatch.delenv("GENERATOR_BASE_URL", raising=False)
    monkeypatch.delenv("GENERATOR_SHARED_SECRET", raising=False)

    response = client.get("/api/generator/jobs/job-123")

    assert response.status_code == 500
    assert response.json()["detail"] == "Generator service is not configured."
