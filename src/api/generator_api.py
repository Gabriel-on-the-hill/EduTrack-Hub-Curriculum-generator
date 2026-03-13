from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel, Field

from src.api.generation_jobs import create_job, get_job, init_generation_job_store, update_status
from src.production.service_adapter import GenerationServiceAdapter

router = APIRouter(prefix="/v1", tags=["generation"])
adapter = GenerationServiceAdapter()


class GenerateRequest(BaseModel):
    curriculum_id: str = Field(min_length=1)
    topic_title: str | None = None
    topic_description: str | None = None
    grade: str | None = None
    jurisdiction: str | None = None
    content_format: str | None = None
    target_level: str | None = None
    provenance: dict | None = None


def _run_generation_job(job_id: str, payload: dict):
    update_status(job_id, "running")
    outcome = adapter.generate(curriculum_id=payload["curriculum_id"], request_payload=payload)
    if outcome["status"] == "succeeded":
        update_status(job_id, "succeeded", result=outcome["result"])
    else:
        update_status(job_id, "failed", error=outcome["error"])


@router.post("/generate")
def create_generation_job(req: GenerateRequest, background_tasks: BackgroundTasks, response: Response):
    init_generation_job_store()
    job_id = str(uuid4())
    payload = req.model_dump()
    create_job(job_id, payload)
    background_tasks.add_task(_run_generation_job, job_id, payload)
    response.status_code = 202
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def get_generation_job(job_id: str):
    init_generation_job_store()
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_id not found")

    result = {
        "job_id": job["job_id"],
        "status": job["status"],
    }
    if job["status"] == "succeeded" and job["result_payload"] is not None:
        result["result"] = job["result_payload"]
    if job["status"] == "failed" and job["error_payload"] is not None:
        result["error"] = job["error_payload"]
    return result
