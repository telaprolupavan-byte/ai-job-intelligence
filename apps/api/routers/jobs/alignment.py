"""GET/POST /jobs/{job_id}/ats and /jobs/{job_id}/gap-analysis: ATS
Alignment (AJI-013, AJI-020) and the Gap Analysis read from it (AJI-015)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import AtsAlignmentResult, GapAnalysis, User
from apps.api.routers.jobs.common import (
    _get_visible_job_or_404,
    _parse_optional_resume_version_id,
)
from apps.api.services.ats_alignment_service import (
    ATSAlignmentServiceError,
    calculate_ats_alignment,
    get_latest_ats_alignment,
)
from apps.api.services.gap_analysis.service import (
    GapAnalysisServiceError,
    generate_gap_analysis,
    get_latest_gap_analysis,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


def _ats_alignment_to_response(record: AtsAlignmentResult) -> dict:
    result_data = record.result

    return {
        "id": str(record.id),
        "job_id": str(record.job_id),
        "resume_version_id": str(record.resume_version_id),
        "job_intelligence_id": str(record.job_intelligence_id),
        "requirement_intelligence_id": (
            str(record.requirement_intelligence_id)
            if record.requirement_intelligence_id
            else None
        ),
        "engine_version": record.engine_version,
        "overall_score": record.overall_score,
        "confidence": record.confidence,
        "scoring_version": result_data["scoring_version"],
        "must_have_total": result_data["must_have_total"],
        "must_have_matched": result_data["must_have_matched"],
        "preferred_total": result_data["preferred_total"],
        "preferred_matched": result_data["preferred_matched"],
        "must_have_ceiling": result_data.get("must_have_ceiling"),
        "score_components": result_data.get("score_components", []),
        "requirement_results": result_data["requirement_results"],
        # AJI-020C: descriptive-only, never scored - see
        # services/ats_alignment/contracts.py's
        # RequirementRelationshipGroup/ScreeningConstraintInfo docstrings.
        # `.get(..., [])` keeps a historical row persisted before this
        # migration (whose `result` JSON predates these keys) readable.
        "relationships": result_data.get("relationships", []),
        "screening_constraints": result_data.get("screening_constraints", []),
        "created_at": record.created_at.isoformat(),
    }


@router.get("/{job_id}/ats")
def get_ats_alignment(
    job_id: str,
    resume_version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated user's most recently computed ATS Alignment
    (AJI-013) result for a job, without recomputing it. 404s when no
    analysis has been generated yet (see POST /jobs/{job_id}/ats).

    ATS Alignment is user-specific (the same job can be analyzed against
    different resumes/users) — a user can only ever read their own
    results, never another user's.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    parsed_resume_version_id = _parse_optional_resume_version_id(
        resume_version_id
    )

    record = get_latest_ats_alignment(
        db,
        user_id=current_user.id,
        job_id=job_uuid,
        resume_version_id=parsed_resume_version_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="ATS Alignment has not been generated for this job yet.",
        )

    return _ats_alignment_to_response(record)


@router.post("/{job_id}/ats")
def create_ats_alignment(
    job_id: str,
    resume_version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute (or idempotently reuse) the ATS Alignment (AJI-013) result
    for the authenticated user against a specific job.

    An explicit `resume_version_id` may be supplied to align against
    that exact ResumeVersion (it must belong to the authenticated user).
    When omitted, the same default resume selection Job Match uses
    applies: the user's most recent Resume, preferring its master
    ResumeVersion.

    Reuses an existing result when the resume version, the underlying
    Job Intelligence snapshot, and the ATS engine version are all
    unchanged; otherwise produces a new, additional result without
    overwriting history.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    parsed_resume_version_id = _parse_optional_resume_version_id(
        resume_version_id
    )

    try:
        record = calculate_ats_alignment(
            db=db,
            current_user=current_user,
            job_id=job_uuid,
            resume_version_id=parsed_resume_version_id,
        )
    except ATSAlignmentServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return _ats_alignment_to_response(record)


def _gap_analysis_to_response(record: GapAnalysis) -> dict:
    return {
        "id": str(record.id),
        "job_id": str(record.job_id),
        "resume_version_id": str(record.resume_version_id),
        "job_intelligence_id": str(record.job_intelligence_id),
        "ats_alignment_id": str(record.ats_alignment_id),
        "analysis_version": record.analysis_version,
        "analyzer_version": record.analyzer_version,
        "prompt_version": record.prompt_version,
        "model_provider": record.model_provider,
        "model_name": record.model_name,
        "generation_status": record.generation_status,
        "must_have_gap_count": record.must_have_gap_count,
        "preferred_gap_count": record.preferred_gap_count,
        "gaps": record.result["gaps"],
        "created_at": record.created_at.isoformat(),
    }


@router.get("/{job_id}/gap-analysis")
def get_gap_analysis(
    job_id: str,
    resume_version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated user's most recently computed Gap Analysis
    & Job-Specific Suggestions (AJI-015) result for a job, without
    recomputing it. 404s when no analysis has been generated yet (see
    POST /jobs/{job_id}/gap-analysis).

    Gap Analysis is user-specific, like ATS Alignment (the same job can
    be analyzed against different resumes/users) — a user can only ever
    read their own results, never another user's.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    parsed_resume_version_id = _parse_optional_resume_version_id(
        resume_version_id
    )

    record = get_latest_gap_analysis(
        db,
        user_id=current_user.id,
        job_id=job_uuid,
        resume_version_id=parsed_resume_version_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Gap Analysis has not been generated for this job yet.",
        )

    return _gap_analysis_to_response(record)


@router.post("/{job_id}/gap-analysis")
def create_gap_analysis(
    job_id: str,
    resume_version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute (or idempotently reuse) the Gap Analysis & Job-Specific
    Suggestions (AJI-015) result for the authenticated user against a
    specific job.

    Every gap is read from the user's ATS Alignment (AJI-013) result for
    the same resume version — computing/reusing it first via the same
    resume-version resolution and idempotent caching
    POST /jobs/{job_id}/ats already uses, never a second, parallel
    requirement-alignment computation. Reuses an existing Gap Analysis
    result when the underlying ATS Alignment result and the analyzer/
    prompt pipeline version are all unchanged; otherwise produces a new,
    additional result without overwriting history.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    parsed_resume_version_id = _parse_optional_resume_version_id(
        resume_version_id
    )

    try:
        record = generate_gap_analysis(
            db=db,
            current_user=current_user,
            job_id=job_uuid,
            resume_version_id=parsed_resume_version_id,
        )
    except GapAnalysisServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return _gap_analysis_to_response(record)
