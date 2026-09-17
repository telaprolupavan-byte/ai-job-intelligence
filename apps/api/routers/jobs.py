from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import Company, Job, User
from apps.api.services.job_match_service import (
    JobMatchServiceError,
    calculate_job_match as calculate_job_match_service,
)


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