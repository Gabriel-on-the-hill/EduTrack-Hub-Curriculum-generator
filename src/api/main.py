"""FastAPI entrypoint for EduTrack API."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from src.api.admin_api import router as admin_router
from src.ingestion.api import router as ingestion_router
from src.ingestion.search_api import router as search_router


class GenerateRequest(BaseModel):
    """Generation request payload."""

    curriculum_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


class JobStatus(BaseModel):
    """In-memory generation job status."""

    job_id: str
    status: str
    curriculum_id: str
    prompt: str
    generated_text: str | None = None
    created_at: str
    completed_at: str | None = None


app = FastAPI(title="EduTrack Curriculum Generator API")
v1_router = APIRouter(prefix="/v1", tags=["v1"])
_jobs: dict[str, JobStatus] = {}


def _engine() -> Any:
    return create_engine(os.getenv("DATABASE_URL", "sqlite:///demo.db"))


@v1_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@v1_router.get("/curricula")
def list_curricula(limit: int = 100) -> dict[str, list[dict[str, Any]]]:
    query = text(
        """
        SELECT id, country, grade, subject, status, source_authority
        FROM curricula
        ORDER BY id
        LIMIT :limit
        """
    )

    with _engine().connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()

    return {"items": [dict(row) for row in rows]}


@v1_router.get("/curricula/{curriculum_id}/competencies")
def list_competencies(curriculum_id: str) -> dict[str, list[dict[str, Any]]]:
    query = text(
        """
        SELECT id, curriculum_id, title, description, order_index
        FROM competencies
        WHERE curriculum_id = :curriculum_id
        ORDER BY order_index, id
        """
    )

    with _engine().connect() as conn:
        rows = conn.execute(query, {"curriculum_id": curriculum_id}).mappings().all()

    return {"items": [dict(row) for row in rows]}


@v1_router.post("/generate")
def generate(request: GenerateRequest) -> dict[str, str]:
    now = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid4())
    generated = (
        f"Generated curriculum artifact for {request.curriculum_id}. "
        f"Prompt: {request.prompt}"
    )

    _jobs[job_id] = JobStatus(
        job_id=job_id,
        status="completed",
        curriculum_id=request.curriculum_id,
        prompt=request.prompt,
        generated_text=generated,
        created_at=now,
        completed_at=now,
    )

    return {"job_id": job_id, "status": "completed"}


@v1_router.get("/jobs/{job_id}")
def get_job(job_id: str) -> JobStatus:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


v1_router.include_router(ingestion_router)
v1_router.include_router(search_router)
v1_router.include_router(admin_router)

app.include_router(v1_router)
