from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import Company, Job, User
from apps.api.services.ats_alignment_service import (
    ATSAlignmentServiceError,
    calculate_ats_alignment,
    get_latest_ats_alignment,
)
from apps.api.services.eligibility_service import (
    evaluate_and_persist_job_eligibility,
)
from apps.api.services.job_intelligence.service import (
    JobIntelligenceServiceError,
    generate_job_intelligence,
    get_latest_job_intelligence,
)
from apps.api.services.job_match_service import (
    JobMatchServiceError,
    calculate_job_match as calculate_job_match_service,
)
from apps.api.models import AtsAlignmentResult, JobIntelligence
from services.eligibility.contracts import EligibilityResult


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.get("")
def list_jobs(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    employment_type: str | None = Query(default=None),
    remote_type: str | None = Query(default=None),
    location: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    query = (
        select(Job, Company.name)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Job.is_active.is_(True))
    )

    if search:
        search_pattern = f"%{search.strip()}%"

        query = query.where(
            Job.title.ilike(search_pattern)
            | Company.name.ilike(search_pattern)
        )

    if employment_type:
        query = query.where(
            Job.employment_type == employment_type
        )

    if remote_type:
        query = query.where(
            Job.remote_type == remote_type
        )

    if location:
        query = query.where(
            Job.location.ilike(f"%{location.strip()}%")
        )

    count_query = select(func.count()).select_from(
        query.subquery()
    )

    total = db.scalar(count_query) or 0

    offset = (page - 1) * page_size

    query = (
        query
        .order_by(
            Job.posting_date.desc().nullslast(),
            Job.id.asc(),
        )
        .offset(offset)
        .limit(page_size)
    )

    results = db.execute(query).all()

    jobs = [
        {
            "id": str(job.id),
            "title": job.title,
            "company": company_name,
            "location": job.location,
            "country": job.country,
            "remote_type": job.remote_type,
            "employment_type": job.employment_type,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "contract_duration": job.contract_duration,
            "contract_worker_type": job.contract_worker_type,
            "description": job.description,
            "requirements": job.requirements,
            "responsibilities": job.responsibilities,
            "posting_date": (
                job.posting_date.isoformat()
                if job.posting_date
                else None
            ),
            "source": job.source,
            "source_url": job.source_url,
            "application_url": job.application_url,
            "first_seen_at": job.first_seen_at.isoformat(),
            "last_seen_at": job.last_seen_at.isoformat(),
        }
        for job, company_name in results
    ]

    return {
        "jobs": jobs,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (
                (total + page_size - 1) // page_size
                if total
                else 0
            ),
        },
    }


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

    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

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

    result_data = match_record.result

    return {
        "id": str(match_record.id),
        "job_id": str(match_record.job_id),
        "resume_version_id": str(match_record.resume_version_id),
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
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    job = db.query(Job).filter(Job.id == job_uuid).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

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
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    job = db.query(Job).filter(Job.id == job_uuid).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

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
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    try:
        record = generate_job_intelligence(db, job_id=job_uuid)
    except JobIntelligenceServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return _job_intelligence_to_response(record)


def _ats_alignment_to_response(record: AtsAlignmentResult) -> dict:
    result_data = record.result

    return {
        "id": str(record.id),
        "job_id": str(record.job_id),
        "resume_version_id": str(record.resume_version_id),
        "job_intelligence_id": str(record.job_intelligence_id),
        "engine_version": record.engine_version,
        "overall_score": record.overall_score,
        "confidence": record.confidence,
        "scoring_version": result_data["scoring_version"],
        "must_have_total": result_data["must_have_total"],
        "must_have_matched": result_data["must_have_matched"],
        "preferred_total": result_data["preferred_total"],
        "preferred_matched": result_data["preferred_matched"],
        "requirement_results": result_data["requirement_results"],
        "created_at": record.created_at.isoformat(),
    }


def _parse_optional_resume_version_id(
    resume_version_id: str | None,
) -> UUID | None:
    if resume_version_id is None:
        return None

    try:
        return UUID(resume_version_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Resume version not found.",
        )


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
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    job = db.query(Job).filter(Job.id == job_uuid).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

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
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

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
