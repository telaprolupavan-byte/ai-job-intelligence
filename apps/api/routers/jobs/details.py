"""GET /jobs/{job_id}: a single job's details (AJI-022)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import User
from apps.api.routers.jobs.common import (
    _get_visible_job_or_404,
    _job_to_response,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.get("/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    A single job the authenticated user can see: any discovered job, or
    one of their own submitted jobs (AJI-022). Another user's submitted
    job 404s exactly like a job that does not exist.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    company_name = job.company.name if job.company is not None else None

    return {
        **_job_to_response(job, company_name),
        "raw_submitted_content": job.raw_submitted_content,
    }
