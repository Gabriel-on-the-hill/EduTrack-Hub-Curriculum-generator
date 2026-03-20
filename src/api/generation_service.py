from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import sessionmaker

from src.production.harness import ModelProvenance, ProductionHarness
from src.production.security import ReadOnlySession


class GenerateJobRequest(BaseModel):
    """Request payload accepted by the asynchronous generation API."""

    curriculum_id: str = Field(min_length=1)
    topic_title: str = Field(min_length=1)
    topic_description: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    jurisdiction: str = Field(default="national", min_length=1)
    content_format: str = Field(default="lesson_plan", min_length=1)
    target_level: str = Field(default="core", min_length=1)
    provenance: dict[str, Any] = Field(default_factory=dict)


class GenerationJobRecord(BaseModel):
    """Durable job representation returned by the polling endpoint."""

    job_id: str
    status: str
    request: GenerateJobRequest
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None


class GenerationExecutor(Protocol):
    async def execute(self, request: GenerateJobRequest) -> dict[str, Any]:
        """Run the underlying generation flow and return a serializable result."""


class ProductionHarnessExecutor:
    """Adapter that runs the existing production harness generation logic."""

    def __init__(self, database_url: str | None = None):
        self._database_url = database_url or "sqlite:///demo.db"
        self._session_factory = sessionmaker(
            bind=create_engine(self._database_url),
            class_=ReadOnlySession,
        )

    async def execute(self, request: GenerateJobRequest) -> dict[str, Any]:
        session = self._session_factory()
        try:
            harness = ProductionHarness(
                db_session=session,
                primary_provenance=ModelProvenance(model_provider="api", model_id="primary"),
                shadow_provenance=ModelProvenance(model_provider="api", model_id="shadow"),
                verify_db_level=False,
            )
            config = SimpleNamespace(
                jurisdiction=request.jurisdiction,
                grade=request.grade,
                topic_title=request.topic_title,
                topic_description=request.topic_description,
                content_format=request.content_format,
                target_level=request.target_level,
            )
            provenance = request.provenance or {"requested_via": "v1_generate_api"}
            output = await harness.generate_artifact(
                curriculum_id=request.curriculum_id,
                config=config,
                provenance=provenance,
            )
            return output.model_dump(mode="json")
        finally:
            session.close()


class GenerationJobStore:
    """Persists generation jobs in a database table so polling survives restarts."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def init_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS generation_jobs (
                        job_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        request_payload TEXT NOT NULL,
                        result_payload TEXT,
                        error_text TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT
                    )
                    """
                )
            )

    def create_job(self, request: GenerateJobRequest) -> GenerationJobRecord:
        job_id = str(uuid4())
        timestamp = self._utc_now()
        payload = request.model_dump(mode="json")
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO generation_jobs (
                        job_id, status, request_payload, created_at, updated_at
                    ) VALUES (
                        :job_id, 'queued', :request_payload, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "job_id": job_id,
                    "request_payload": self._to_json(payload),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> GenerationJobRecord:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        job_id,
                        status,
                        request_payload,
                        result_payload,
                        error_text,
                        created_at,
                        updated_at,
                        started_at,
                        completed_at
                    FROM generation_jobs
                    WHERE job_id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()

        if row is None:
            raise KeyError(job_id)

        return GenerationJobRecord(
            job_id=row["job_id"],
            status=row["status"],
            request=GenerateJobRequest.model_validate(self._from_json(row["request_payload"])),
            result=self._from_json(row["result_payload"]),
            error=row["error_text"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def mark_running(self, job_id: str) -> None:
        timestamp = self._utc_now()
        self._update_job(
            job_id,
            {
                "status": "running",
                "started_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        timestamp = self._utc_now()
        self._update_job(
            job_id,
            {
                "status": "succeeded",
                "result_payload": self._to_json(result),
                "error_text": None,
                "updated_at": timestamp,
                "completed_at": timestamp,
            },
        )

    def mark_failed(self, job_id: str, error: str) -> None:
        timestamp = self._utc_now()
        self._update_job(
            job_id,
            {
                "status": "failed",
                "error_text": error,
                "updated_at": timestamp,
                "completed_at": timestamp,
            },
        )

    def _update_job(self, job_id: str, fields: dict[str, Any]) -> None:
        assignments = ", ".join(f"{column} = :{column}" for column in fields)
        params = {"job_id": job_id, **fields}
        with self._engine.begin() as conn:
            result = conn.execute(
                text(f"UPDATE generation_jobs SET {assignments} WHERE job_id = :job_id"),
                params,
            )
        if result.rowcount == 0:
            raise KeyError(job_id)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()  # noqa: UP017

    @staticmethod
    def _to_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True)

    @staticmethod
    def _from_json(payload: str | None) -> dict[str, Any] | None:
        if payload is None:
            return None
        return json.loads(payload)


class GenerationService:
    """Coordinates queued job creation and the async execution lifecycle."""

    def __init__(self, store: GenerationJobStore, executor: GenerationExecutor):
        self._store = store
        self._executor = executor
        self._store.init_schema()

    def enqueue(self, request: GenerateJobRequest) -> GenerationJobRecord:
        return self._store.create_job(request)

    def get_job(self, job_id: str) -> GenerationJobRecord:
        return self._store.get_job(job_id)

    async def process_job(self, job_id: str) -> GenerationJobRecord:
        job = self._store.get_job(job_id)
        self._store.mark_running(job_id)

        try:
            result = await self._executor.execute(job.request)
        except Exception as exc:
            self._store.mark_failed(job_id, str(exc))
            return self._store.get_job(job_id)

        self._store.mark_succeeded(job_id, result)
        return self._store.get_job(job_id)


@lru_cache(maxsize=1)
def get_generation_service() -> GenerationService:
    import os

    database_url = os.getenv("DATABASE_URL", "sqlite:///demo.db")
    engine = create_engine(database_url)
    store = GenerationJobStore(engine)
    executor = ProductionHarnessExecutor(database_url=database_url)
    return GenerationService(store=store, executor=executor)
