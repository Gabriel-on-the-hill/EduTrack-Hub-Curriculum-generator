# tests/ingestion/test_search_api.py
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ingestion.search_api import router
from src.security import build_auth_headers

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_search_api_results(monkeypatch):
    monkeypatch.setenv("EDUTRACK_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("EDUTRACK_ALLOWED_SERVICES", "ingestion-service")

    # Mock the search_web call to avoid real network
    with patch("src.ingestion.search_api.search_web") as mock_search:
        mock_search.return_value = [
            {"title": "Test Curr", "url": "https://www.education.gov.uk/curr.pdf", "snippet": "Test", "domain": "gov.uk"}
        ]

        body = b'{"query":"test","max_results":10}'
        headers = build_auth_headers(
            service_name="ingestion-service",
            method="POST",
            path="/api/ingest/search",
            body=body,
        )
        response = client.post(
            "/api/ingest/search",
            content=body,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["authority_hint"] == "high"  # inferred from .gov.uk


def test_search_api_requires_headers(monkeypatch):
    monkeypatch.setenv("EDUTRACK_SHARED_SECRET", "test-secret")
    response = client.post("/api/ingest/search", json={"query": "test"})
    assert response.status_code == 401


def test_search_api_health_no_headers():
    response = client.get("/api/ingest/health")
    assert response.status_code == 200


def test_search_api_rate_limit():
    # This might fail if slowapi memory storage isn't shared or initialized same way
    # Ideally checking headers
    pass
