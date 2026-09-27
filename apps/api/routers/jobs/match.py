"""GET/POST /jobs/{job_id}/match: Job Match scoring (AJI-007, AJI-014,
AJI-019)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import JobMatchResult, User
from apps.api.routers.jobs.common import (
    _get_visible_job_or_404,
    _parse_optional_resume_version_id,
)
from apps.api.services.job_match_service import (
    JobMatchServiceError,
    calculate_job_match as calculate_job_match_service,
    get_latest_job_match,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


def _job_match_to_response(match_record: JobMatchResult) -> dict:
    result_data = match_record.result

    return {
        "id": str(match_record.id),
        "job_id": str(match_record.job_id),
        "resume_version_id": str(match_record.resume_version_id),
        "job_intelligence_id": (
            str(match_record.job_intelligence_id)
            if match_record.job_intelligence_id
            else None
        ),
        "score": match_record.score,
        "confidence": match_record.confidence,
        "engine_version": match_record.engine_version,
        "strengths": result_data["strengths"],
        "skill_gaps": result_data["skill_gaps"],
        "components": result_data["components"],
        "must_have_matches": result_data["must_have_matches"],
        "must_have_gaps": result_data["must_have_gaps"],
        "preferred_matches": result_data["preferred_matches"],
        "preferred_gaps": result_data["preferred_gaps"],
    }


@router.get("/{job_id}/match")
def get_job_match(
    job_id: str,
    resume_version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated user's most recently calculated Job Match
    for a job, without recomputing it (AJI-023). 404s when no match has
    been calculated yet (see POST /jobs/{job_id}/match).

    The read counterpart of the POST, like GET /ats and GET /gap-analysis:
    it lets the Jobs page show a job's existing Match next to its existing
    ATS Alignment and Gap Analysis instead of recalculating to see them.
    Job Match is user-specific - a user only ever reads their own rows.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)

    parsed_resume_version_id = _parse_optional_resume_version_id(
        resume_version_id
    )

    record = get_latest_job_match(
        db,
        user_id=current_user.id,
        job_id=job.id,
        resume_version_id=parsed_resume_version_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Job Match has not been calculated for this job yet.",
        )

    return _job_match_to_response(record)


@router.post("/{job_id}/match")
def calculate_job_match(
    job_id: str,
    resume_version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate and persist a deterministic Job Match Score for the
    authenticated user against a specific job.

    An explicit `resume_version_id` may be supplied to calculate the
    match against that exact ResumeVersion (it must belong to the
    authenticated user). When omitted, the existing default behavior
    applies: the user's most recent Resume, preferring its master
    ResumeVersion.
    """

    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    parsed_resume_version_id: UUID | None = None

    if resume_version_id is not None:
        try:
            parsed_resume_version_id = UUID(resume_version_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Resume version not found.",
            )

    try:
        match_record = calculate_job_match_service(
            db=db,
            current_user=current_user,
            job_id=job_uuid,
            resume_version_id=parsed_resume_version_id,
        )
    except JobMatchServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return _job_match_to_response(match_record)
