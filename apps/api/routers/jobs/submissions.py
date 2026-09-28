"""POST /jobs/submissions: user job submission (AJI-022)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import User
from apps.api.routers.jobs.common import _job_to_response
from apps.api.routers.jobs.intelligence import (
    _job_intelligence_to_response,
    _requirement_intelligence_to_response,
)
from apps.api.schemas import JobSubmissionRequest
from apps.api.services.job_submission.service import (
    JobSubmissionServiceError,
    submit_job,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.post("/submissions")
def create_job_submission(
    payload: JobSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit pasted job content (AJI-022) and analyze it synchronously.

    Creates a job private to the authenticated user (`source =
    "user_submitted"`), keeping the complete raw paste, then runs the
    existing Job Intelligence (AJI-012) and Requirement Intelligence
    (AJI-020A/B) pipelines on it. The pasted text is treated purely as
    untrusted job-description data. Resubmitting identical content reuses
    the same job rather than creating a duplicate, so retrying after a
    failed analysis is safe.

    No URL ingestion or scraping: only the pasted text is ever read.
    """
    try:
        result = submit_job(
            db,
            current_user=current_user,
            content=payload.content,
            title=payload.title,
            company=payload.company,
        )
    except JobSubmissionServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": str(exc),
                "job_id": str(exc.job_id) if exc.job_id else None,
            },
        ) from exc

    job = result.job
    company_name = job.company.name if job.company is not None else None

    return {
        "job": {
            **_job_to_response(job, company_name),
            "raw_submitted_content": job.raw_submitted_content,
        },
        "intelligence": _job_intelligence_to_response(
            result.job_intelligence
        ),
        "requirement_intelligence": _requirement_intelligence_to_response(
            result.requirement_intelligence
        ),
        "security": {
            "prompt_injection_detected": bool(result.injection_signals),
            "signals": [
                signal.model_dump() for signal in result.injection_signals
            ],
        },
    }
