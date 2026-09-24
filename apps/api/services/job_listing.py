"""The Jobs listing query (the base of GET /jobs), shared with AJI-025.

Extracted unchanged from `apps/api/routers/jobs.py::list_jobs` so that the
personalized priority view (GET /jobs/priority) scopes jobs with exactly
the same active/visibility/filter semantics as the public listing, rather
than a second copy of those rules drifting apart from it.

AJI-023 (Job Search) adds the search-criteria contract both endpoints
validate against: the filter vocabularies below and the free-text limits.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import Select, select

from apps.api.models import Company, Job
from apps.api.services.job_access import visible_jobs_filter


# The only values discovery normalization can store in `Job.employment_type`
# / `Job.remote_type` (services/job_discovery/normalizer.py; a test pins the
# two together). Filtering by anything else could only ever return zero
# jobs, so it is rejected as a 422 instead of looking like "no results".
EmploymentTypeFilter = Literal[
    "full_time",
    "part_time",
    "contract",
    "internship",
    "temporary",
]
RemoteTypeFilter = Literal["remote", "hybrid", "onsite"]

# Upper bound for the free-text criteria (`search`, `location`). Generous
# for any real role/company/place name; it exists so a pathological value
# is a 422 rather than an arbitrarily large LIKE pattern.
SEARCH_TEXT_MAX_LENGTH = 200

_LIKE_ESCAPE = "\\"


def clean_search_text(value: str | None) -> str | None:
    """Trim a free-text criterion; blank means "no criterion"."""
    if value is None:
        return None

    cleaned = " ".join(value.split())

    return cleaned or None


def _contains_pattern(value: str) -> str:
    """ILIKE pattern matching `value` literally: a user typing `%` or `_`
    searches for that character, not for a wildcard."""
    escaped = (
        value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", f"{_LIKE_ESCAPE}%")
        .replace("_", f"{_LIKE_ESCAPE}_")
    )

    return f"%{escaped}%"


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

    search = clean_search_text(search)
    location = clean_search_text(location)

    if search:
        search_pattern = _contains_pattern(search)

        query = query.where(
            Job.title.ilike(search_pattern, escape=_LIKE_ESCAPE)
            | Company.name.ilike(search_pattern, escape=_LIKE_ESCAPE)
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
            Job.location.ilike(
                _contains_pattern(location), escape=_LIKE_ESCAPE
            )
        )

    return query
