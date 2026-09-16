from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.models import Company, Job

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

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    offset = (page - 1) * page_size

    query = (
        query
        .order_by(Job.posting_date.desc().nullslast(), Job.id.asc())
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