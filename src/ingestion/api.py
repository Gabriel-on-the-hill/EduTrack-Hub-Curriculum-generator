from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .worker import ingest_sync
from .services import get_ingestion_job, update_ingestion_job

router = APIRouter()


class IngestRequest(BaseModel):
    url: str
    requested_by: str = "system"


@router.post("/hub/jobs")
def submit_job(request: IngestRequest):
    result = ingest_sync(request.url, requested_by=request.requested_by)
    job_id = result.get("job_id")
    return {"status": result["status"], "job_id": job_id, "result": result}


@router.get("/hub/jobs/{job_id}")
def poll_job(job_id: str):
    job = get_ingestion_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/hub/jobs/{job_id}/save")
def save_job(job_id: str):
    job = get_ingestion_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "success":
        raise HTTPException(status_code=409, detail="Only successful jobs can be saved")
    update_ingestion_job(job_id, status="saved", result_payload=job["result_payload"])
    return {"ok": True, "job_id": job_id, "status": "saved", "result_payload": job["result_payload"]}
