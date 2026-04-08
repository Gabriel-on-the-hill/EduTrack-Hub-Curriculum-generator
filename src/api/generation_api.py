from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from src.api.generation_service import (
    GenerateJobRequest,
    GenerationJobRecord,
    GenerationService,
    get_generation_service,
)

router = APIRouter()
GenerationServiceDependency = Annotated[GenerationService, Depends(get_generation_service)]


@router.post(
    "/v1/generate",
    response_model=GenerationJobRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_generation_job(
    request: GenerateJobRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    service: GenerationServiceDependency,
) -> GenerationJobRecord:
    job = service.enqueue(request)
    response.headers["Location"] = f"/v1/jobs/{job.job_id}"
    background_tasks.add_task(service.process_job, job.job_id)
    return job


@router.get("/v1/jobs/{job_id}", response_model=GenerationJobRecord)
def get_generation_job(
    job_id: str,
    service: GenerationServiceDependency,
) -> GenerationJobRecord:
    try:
        return service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
