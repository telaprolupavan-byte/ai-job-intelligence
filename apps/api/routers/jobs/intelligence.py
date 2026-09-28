"""GET/POST /jobs/{job_id}/intelligence and
/jobs/{job_id}/requirement-intelligence: Job Intelligence (AJI-012) and
Requirement Intelligence (AJI-020A/B)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import JobIntelligence, RequirementIntelligence, User
from apps.api.routers.jobs.common import _get_visible_job_or_404
from apps.api.services.job_intelligence.service import (
    JobIntelligenceServiceError,
    generate_job_intelligence,
    get_latest_job_intelligence,
)
from apps.api.services.requirement_intelligence.persistence_service import (
    RequirementIntelligencePersistenceError,
    generate_requirement_intelligence,
    get_latest_requirement_intelligence,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


def _job_intelligence_to_response(record: JobIntelligence) -> dict:
    return {
        "id": str(record.id),
        "job_id": str(record.job_id),
        "content_fingerprint": record.content_fingerprint,
        "analysis_version": record.analysis_version,
        "analyzer_version": record.analyzer_version,
        "prompt_version": record.prompt_version,
        "model_provider": record.model_provider,
        "model_name": record.model_name,
        "extraction_status": record.extraction_status,
        "source": record.source,
        "source_url": record.source_url,
        "created_at": record.created_at.isoformat(),
        "intelligence": record.structured_intelligence,
    }


@router.get("/{job_id}/intelligence")
def get_job_intelligence(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the most recently computed Job Intelligence (AJI-012) snapshot
    for a job, without recomputing it. 404s when no snapshot has been
    generated yet (see POST /jobs/{job_id}/intelligence).

    Job Intelligence is shared, job-scoped data — never user-specific —
    but this endpoint still requires authentication like the rest of the
    per-job API surface, and never triggers an AI call on read.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    record = get_latest_job_intelligence(db, job_id=job_uuid)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Job Intelligence has not been generated for this job yet.",
        )

    return _job_intelligence_to_response(record)


@router.post("/{job_id}/intelligence")
def create_job_intelligence(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute (or idempotently reuse) the Job Intelligence snapshot for a
    job. Reuses an existing snapshot when the job's observable content
    and the analyzer/prompt pipeline version are unchanged; otherwise
    produces a new, additional snapshot without overwriting history.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    try:
        record = generate_job_intelligence(db, job_id=job_uuid)
    except JobIntelligenceServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return _job_intelligence_to_response(record)


def _requirement_intelligence_to_response(record: RequirementIntelligence) -> dict:
    return {
        "id": str(record.id),
        "job_id": str(record.job_id),
        "content_fingerprint": record.content_fingerprint,
        "analysis_version": record.analysis_version,
        "analyzer_version": record.analyzer_version,
        "prompt_version": record.prompt_version,
        "model_provider": record.model_provider,
        "model_name": record.model_name,
        "extraction_status": record.extraction_status,
        "created_at": record.created_at.isoformat(),
        "intelligence": record.structured_intelligence,
    }


@router.get("/{job_id}/requirement-intelligence")
def get_requirement_intelligence(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated user's most recently computed Requirement
    Intelligence (AJI-020A/AJI-020B) snapshot for a job, without
    recomputing it. 404s when no snapshot has been generated yet (see
    POST /jobs/{job_id}/requirement-intelligence).

    Requirement Intelligence is persisted per-user (see
    apps/api/models.py's `RequirementIntelligence` docstring) — a user
    can only ever read their own snapshots, never another user's.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    record = get_latest_requirement_intelligence(
        db, user_id=current_user.id, job_id=job_uuid
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Requirement Intelligence has not been generated for "
            "this job yet.",
        )

    return _requirement_intelligence_to_response(record)


@router.post("/{job_id}/requirement-intelligence")
def create_requirement_intelligence(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute (or idempotently reuse) the Requirement Intelligence
    (AJI-020A/AJI-020B) snapshot for the authenticated user against a
    job. Reuses an existing snapshot when the job's observable content,
    the analyzer/prompt pipeline version, and the configured AI
    provider/model are all unchanged; otherwise produces a new,
    additional snapshot without overwriting history.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    try:
        record = generate_requirement_intelligence(
            db, user_id=current_user.id, job_id=job_uuid
        )
    except RequirementIntelligencePersistenceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return _requirement_intelligence_to_response(record)
