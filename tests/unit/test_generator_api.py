from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import generator_api
from src.api.generator_api import router


def _make_client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'jobs.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_create_generation_job_returns_202_and_job_id(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/v1/generate", json={"curriculum_id": "cur-1"})

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body


def test_get_job_status_succeeded(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    monkeypatch.setattr(
        generator_api.adapter,
        "generate",
        lambda **kwargs: {"status": "succeeded", "result": {"content_markdown": "ok", "metrics": {}, "metadata": {}}},
    )

    create = client.post("/v1/generate", json={"curriculum_id": "cur-2"})
    job_id = create.json()["job_id"]

    status = client.get(f"/v1/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"


def test_get_job_status_failed(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    monkeypatch.setattr(
        generator_api.adapter,
        "generate",
        lambda **kwargs: {"status": "failed", "error": {"type": "RuntimeError", "message": "boom", "retryable": True}},
    )

    create = client.post("/v1/generate", json={"curriculum_id": "cur-3"})
    job_id = create.json()["job_id"]

    status = client.get(f"/v1/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "failed"
    assert body["error"]["type"] == "RuntimeError"


def test_generation_job_persists_across_store_reinit(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    monkeypatch.setattr(
        generator_api.adapter,
        "generate",
        lambda **kwargs: {"status": "succeeded", "result": {"content_markdown": "persist", "metrics": {}, "metadata": {}}},
    )

    create = client.post("/v1/generate", json={"curriculum_id": "cur-4"})
    job_id = create.json()["job_id"]

    # Simulate process restart: table init reruns; data should still be present.
    generator_api.init_generation_job_store()

    status = client.get(f"/v1/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"
