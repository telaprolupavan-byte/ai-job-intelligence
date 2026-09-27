"""GET /jobs/priority: job priority ordering (AJI-025).

Must be registered before GET /jobs/{job_id} - see this package's
__init__.py."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import User
from apps.api.routers.jobs.common import (
    _job_to_response,
    _parse_optional_resume_version_id,
)
from apps.api.services.job_listing import (
    SEARCH_TEXT_MAX_LENGTH,
    EmploymentTypeFilter,
    RemoteTypeFilter,
)
from apps.api.services.priority_ranking_service import (
    PriorityItem,
    PriorityRankingServiceError,
    build_job_priority,
)
from services.priority_ranking.engine import (
    ENGINE_VERSION as PRIORITY_ENGINE_VERSION,
    ORDERING as PRIORITY_ORDERING,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


def _priority_item_to_response(item: PriorityItem) -> dict:
    result = item.result
    match = item.job_match
    ats = item.ats_alignment

    return {
        "job": _job_to_response(item.job, item.company_name),
        "rank": result.rank,
        "state": result.state.value,
        "eligibility_status": result.eligibility_status,
        "reasons": [
            {
                "code": reason.code,
                "source": reason.source,
                "kind": reason.kind,
                "message": reason.message,
            }
            for reason in result.reasons
        ],
        "blocking_factors": [
            {
                "code": factor.code,
                "source": factor.source,
                "message": factor.message,
            }
            for factor in result.blocking_factors
        ],
        # The exact inputs the ordering read, so a result can always be
        # traced to (and reconciled with) the job's own Match/ATS results.
        "inputs": {
            "eligibility": {
                "status": item.eligibility.status.value,
                "engine_version": item.eligibility.engine_version,
                "failed_constraints": item.eligibility.failed_constraints,
                "unknown_constraints": item.eligibility.unknown_constraints,
            },
            "job_match": (
                {
                    "id": str(match.id),
                    "score": match.score,
                    "confidence": match.confidence,
                    "engine_version": match.engine_version,
                    "job_intelligence_id": (
                        str(match.job_intelligence_id)
                        if match.job_intelligence_id
                        else None
                    ),
                    "current": result.job_match_current,
                    "created_at": match.created_at.isoformat(),
                }
                if match is not None
                else None
            ),
            "ats_alignment": (
                {
                    "id": str(ats.id),
                    "overall_score": ats.overall_score,
                    "confidence": ats.confidence,
                    "must_have_matched": ats.result.get("must_have_matched"),
                    "must_have_total": ats.result.get("must_have_total"),
                    "engine_version": ats.engine_version,
                    "requirement_intelligence_id": (
                        str(ats.requirement_intelligence_id)
                        if ats.requirement_intelligence_id
                        else None
                    ),
                    "current": result.ats_alignment_current,
                    "created_at": ats.created_at.isoformat(),
                }
                if ats is not None
                else None
            ),
        },
    }


# Registered before GET /{job_id} (see __init__.py) so "priority" is never
# read as a job id.
@router.get("/priority")
def get_job_priority(
    resume_version_id: str | None = Query(default=None),
    # AJI-023 (Job Search): invalid criteria are a 422, never a silent
    # empty result - see apps/api/services/job_listing.py.
    search: str | None = Query(
        default=None, max_length=SEARCH_TEXT_MAX_LENGTH
    ),
    employment_type: EmploymentTypeFilter | None = Query(default=None),
    remote_type: RemoteTypeFilter | None = Query(default=None),
    location: str | None = Query(
        default=None, max_length=SEARCH_TEXT_MAX_LENGTH
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Order the authenticated user's analyzed jobs for their attention
    (AJI-025). Read-only and deterministic: it never calculates a missing
    analysis, never calls an AI provider, and never changes an
    application.

    Hard Eligibility (evaluated fresh) is a gate - an ineligible job is
    `excluded` and never ranked. The rest are ordered by Job Match, then
    ATS Alignment, for ONE resume version (`resume_version_id`, or the
    same default Job Match uses), then by the listing's own order. Job
    Match and ATS Alignment are never combined into one number; there is
    no priority score. A job with no Job Match for that version is
    `not_ready` and gets no rank.

    Only jobs this user has a Job Match or ATS Alignment for (for that
    resume version) are listed; the rest are counted in
    `counts.unanalyzed`. Uses the same visibility and filters as GET /jobs,
    so another user's private job can never appear. Personalized, so -
    unlike GET /jobs - it always requires authentication.
    """
    parsed_resume_version_id = _parse_optional_resume_version_id(
        resume_version_id
    )

    try:
        outcome = build_job_priority(
            db,
            current_user=current_user,
            resume_version_id=parsed_resume_version_id,
            search=search,
            employment_type=employment_type,
            remote_type=remote_type,
            location=location,
            page=page,
            page_size=page_size,
        )
    except PriorityRankingServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    resume_version = outcome.resume_version

    return {
        "engine_version": PRIORITY_ENGINE_VERSION,
        "ordering": list(PRIORITY_ORDERING),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(current_user.id),
        "resume_version": (
            {
                "id": str(resume_version.id),
                "name": resume_version.name,
                "resume_filename": resume_version.resume.filename,
                "is_master": resume_version.is_master,
            }
            if resume_version is not None
            else None
        ),
        "counts": {
            **outcome.state_counts,
            "unanalyzed": outcome.unanalyzed_count,
        },
        "items": [
            _priority_item_to_response(item) for item in outcome.items
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": outcome.total,
            "total_pages": (
                (outcome.total + page_size - 1) // page_size
                if outcome.total
                else 0
            ),
        },
    }
