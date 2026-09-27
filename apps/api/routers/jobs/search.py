"""GET /jobs: the paginated, filterable job catalog (AJI-006, AJI-022,
AJI-023 Job Search)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_optional_current_user
from apps.api.models import Job, User
from apps.api.routers.jobs.common import _job_to_response
from apps.api.services.job_listing import (
    SEARCH_TEXT_MAX_LENGTH,
    EmploymentTypeFilter,
    RemoteTypeFilter,
    job_listing_query,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.get("")
def list_jobs(
    db: Session = Depends(get_db),
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
    # Annotated so a direct Python call (existing tests) defaults to the
    # anonymous view instead of receiving the Depends marker itself.
    current_user: Annotated[
        User | None, Depends(get_optional_current_user)
    ] = None,
):
    # AJI-022 visibility + the optional filters, shared with the AJI-025
    # priority view so both scope jobs identically.
    query = job_listing_query(
        user_id=current_user.id if current_user is not None else None,
        search=search,
        employment_type=employment_type,
        remote_type=remote_type,
        location=location,
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
        _job_to_response(job, company_name)
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
