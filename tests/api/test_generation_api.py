from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from src.api.app import create_app
from src.api.generation_service import (
    GenerateJobRequest,
    GenerationJobStore,
    GenerationService,
    get_generation_service,
)


class SuccessfulExecutor:
    async def execute(self, request: GenerateJobRequest) -> dict[str, object]:
        return {
            "content_markdown": f"# {request.topic_title}\n\nCitation: grounded content",
            "metadata": {"curriculum_id": request.curriculum_id},
        }


class FailingExecutor:
    async def execute(self, request: GenerateJobRequest) -> dict[str, object]:
        raise RuntimeError(f"Generation failed for {request.curriculum_id}")


class BlockingExecutor:
    def __init__(self) -> None:
        self.seen_status: str | None = None
        self._store: GenerationJobStore | None = None

    def bind(self, store: GenerationJobStore) -> BlockingExecutor:
        self._store = store
        return self

    async def execute(self, request: GenerateJobRequest) -> dict[str, object]:
        assert self._store is not None
        with self._store._engine.connect() as conn:
            jobs = list(
                conn.execute(text("SELECT status FROM generation_jobs")).scalars()
            )
        self.seen_status = jobs[0]
        return {"ok": True, "curriculum_id": request.curriculum_id}


REQUEST_PAYLOAD = {
    "curriculum_id": "ng-bio-ss1",
    "topic_title": "Cell Division",
    "topic_description": "Explain mitosis and meiosis.",
    "grade": "SS1",
}


def _build_service(db_path: Path, executor: object) -> GenerationService:
    engine = create_engine(f"sqlite:///{db_path}")
    store = GenerationJobStore(engine)
    if hasattr(executor, "bind"):
        executor.bind(store)
    return GenerationService(store=store, executor=executor)


def test_create_job_returns_202_and_persists_result(tmp_path: Path) -> None:
    db_path = tmp_path / "generation.db"
    service = _build_service(db_path, SuccessfulExecutor())

    app = create_app()
    app.dependency_overrides[get_generation_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/v1/generate", json=REQUEST_PAYLOAD)

    assert response.status_code == 202
    job = response.json()
    assert response.headers["location"] == f"/v1/jobs/{job['job_id']}"
    assert job["status"] == "queued"

    restart_service = _build_service(db_path, SuccessfulExecutor())
    restarted_app = create_app()
    restarted_app.dependency_overrides[get_generation_service] = lambda: restart_service

    with TestClient(restarted_app) as client:
        fetched = client.get(f"/v1/jobs/{job['job_id']}")

    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "succeeded"
    assert body["result"]["metadata"]["curriculum_id"] == "ng-bio-ss1"
    assert body["completed_at"] is not None


def test_job_transitions_to_running_before_success(tmp_path: Path) -> None:
    db_path = tmp_path / "transitions.db"
    executor = BlockingExecutor()
    service = _build_service(db_path, executor)

    app = create_app()
    app.dependency_overrides[get_generation_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/v1/generate", json=REQUEST_PAYLOAD)

    assert response.status_code == 202
    assert executor.seen_status == "running"


def test_failed_job_returns_error_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "failed.db"
    service = _build_service(db_path, FailingExecutor())

    app = create_app()
    app.dependency_overrides[get_generation_service] = lambda: service

    with TestClient(app) as client:
        created = client.post("/v1/generate", json=REQUEST_PAYLOAD)
        failed = client.get(f"/v1/jobs/{created.json()['job_id']}")

    assert created.status_code == 202
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert "Generation failed for ng-bio-ss1" in failed.json()["error"]


def test_unknown_job_returns_404(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    service = _build_service(db_path, SuccessfulExecutor())

    app = create_app()
    app.dependency_overrides[get_generation_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/v1/jobs/does-not-exist")

    assert response.status_code == 404
