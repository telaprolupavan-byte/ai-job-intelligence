"""GET /jobs/{job_id}/eligibility: Hard Eligibility (AJI-011)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import User
from apps.api.routers.jobs.common import _get_visible_job_or_404
from apps.api.services.eligibility_service import (
    evaluate_and_persist_job_eligibility,
)
from services.eligibility.contracts import EligibilityResult


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


def _eligibility_result_to_response(
    job_id: UUID,
    result: EligibilityResult,
    *,
    record_id: UUID,
    evaluated_at,
) -> dict:
    return {
        "id": str(record_id),
        "job_id": str(job_id),
        "status": result.status.value,
        "engine_version": result.engine_version,
        "checks": [
            {
                "constraint": check.constraint,
                "status": check.status.value,
                "reason": check.reason,
            }
            for check in result.checks
        ],
        "failed_constraints": result.failed_constraints,
        "unknown_constraints": result.unknown_constraints,
        "reasons": result.reasons,
        "evaluated_at": evaluated_at.isoformat(),
    }


@router.get("/{job_id}/eligibility")
def get_job_eligibility(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate deterministic Hard Eligibility (AJI-011) for the
    authenticated user against a specific job.

    This is intentionally separate from /jobs/{job_id}/match: eligibility
    is a hard pre-filter (ELIGIBLE/INELIGIBLE/UNKNOWN with explainable
    checks), never a score. The result is recalculated query-time from
    the user's current Preference/Profile and the job's current data, and
    then upserted into JobEligibilityResult (one row per user/job,
    overwritten in place) so a later AJI-012/AJI-013 consumer can read
    the job's current hard-eligibility status without recomputing it. See
    docs/ARCHITECTURE.md for the full hard-vs-soft rationale. Public job
    browsing (GET /jobs) never exposes this personalized data; this
    endpoint always requires authentication.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    result, record = evaluate_and_persist_job_eligibility(
        db=db,
        current_user=current_user,
        job=job,
    )

    return _eligibility_result_to_response(
        job.id,
        result,
        record_id=record.id,
        evaluated_at=record.updated_at,
    )
