from fastapi import APIRouter, HTTPException, Depends

from app.backend.schemas.generation import JobStatusResponse
from app.backend.services.store import JOBS
from app.backend.api.deps import get_current_customer

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, customer: dict = Depends(get_current_customer)):
    job = JOBS.get(job_id)
    if not job or job.get("customer_id") != customer["customer_id"]:
        raise HTTPException(404, "job not found")
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        current_step=job["current_step"],
        completed_count=job["completed_count"],
        total_count=job["total_count"],
        estimated_seconds=job["estimated_seconds"],
    )
