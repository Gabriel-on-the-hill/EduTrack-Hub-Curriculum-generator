# src/api/admin_api.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.security import validate_signed_request
# import service functions - assumes they are added to services.py
from src.ingestion.services import list_pending_jobs, approve_ingestion_job, reject_ingestion_job

router = APIRouter(prefix="/api/admin")


@router.get("/pending_jobs")
def pending_jobs(_: None = Depends(validate_signed_request)):
    return {"jobs": list_pending_jobs()}


class JobAction(BaseModel):
    job_id: str


@router.post("/approve")
def approve(job: JobAction, _: None = Depends(validate_signed_request)):
    ok = approve_ingestion_job(job.job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Approve failed")
    return {"ok": True}


@router.post("/reject")
def reject(job: JobAction, _: None = Depends(validate_signed_request)):
    ok = reject_ingestion_job(job.job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Reject failed")
    return {"ok": True}


@router.get("/health")
def health():
    return {"status": "ok"}
