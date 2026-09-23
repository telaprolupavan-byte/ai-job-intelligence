"""The Jobs listing query (the base of GET /jobs), shared with AJI-025.

Extracted unchanged from `apps/api/routers/jobs.py::list_jobs` so that the
personalized priority view (GET /jobs/priority) scopes jobs with exactly
the same active/visibility/filter semantics as the public listing, rather
than a second copy of those rules drifting apart from it.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from apps.api.models import Company, Job
from apps.api.services.job_access import visible_jobs_filter


def job_listing_query(
    *,
    user_id: UUID | None,
    search: str | None = None,
    employment_type: str | None = None,
    remote_type: str | None = None,
    location: str | None = None,
) -> Select:
    """`select(Job, Company.name)` for the active jobs `user_id` may see,
    narrowed by the listing's optional filters. Unordered and unpaginated -
    callers add their own ordering."""
    query = (
        select(Job, Company.name)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Job.is_active.is_(True))
        # AJI-022: discovered jobs for everyone; a signed-in user also
        # sees their own submitted jobs, never anyone else's.
        .where(visible_jobs_filter(user_id))
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

    return query
