# src/api/admin_api.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
# import service functions - assumes they are added to services.py
from src.ingestion.services import list_pending_jobs, approve_ingestion_job, reject_ingestion_job
from src.api.auth import verify_admin_headers

router = APIRouter(prefix="/api/admin")

@router.get("/pending_jobs", dependencies=[Depends(verify_admin_headers)])
def pending_jobs():
    return {"jobs": list_pending_jobs()}

class JobAction(BaseModel):
    job_id: str

@router.post("/approve", dependencies=[Depends(verify_admin_headers)])
def approve(job: JobAction):
    ok = approve_ingestion_job(job.job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Approve failed")
    return {"ok": True}

@router.post("/reject", dependencies=[Depends(verify_admin_headers)])
def reject(job: JobAction):
    ok = reject_ingestion_job(job.job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Reject failed")
    return {"ok": True}
