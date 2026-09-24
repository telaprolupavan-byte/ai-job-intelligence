"""Job visibility / ownership rules (AJI-022).

A `Job` is either discovered (`submitted_by_user_id IS NULL`, shared with
every user - the only kind that existed before AJI-022) or user-submitted
(private to the user whose id is in that column). Every per-job read or
write goes through `visible_jobs_filter()`/`get_visible_job()` so this
rule lives in exactly one place.

A job the caller cannot see is reported exactly like a job that does not
exist (a plain 404 "Job not found"), so another user's private job id is
never confirmed to exist.

AJI-024: jobs produced by the synthetic test-fixture discovery provider are
invisible to everyone unless test mode (`JOB_DISCOVERY_ENABLE_TEST_PROVIDER`)
is on, so fixture data can never surface as production data - even if such
rows exist in a database that later has test mode turned off. AJI-030
extends this to every source in `NON_PRODUCTION_SOURCES` (the fixture and
the development dataset).

AJI-028: `active_jobs_filter()` is the one definition of a job that is
still open - every listing-style query (GET /jobs, GET /jobs/priority via
`job_listing_query`, the dashboard counts) uses it instead of repeating
its own `is_active` check.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import Job
from services.job_discovery.sources.non_production import (
    NON_PRODUCTION_SOURCES,
)


def visible_jobs_filter(user_id: UUID | None):
    """SQL filter for the jobs `user_id` may see.

    `None` (an anonymous caller) sees discovered jobs only.
    """
    if user_id is None:
        ownership = Job.submitted_by_user_id.is_(None)
    else:
        ownership = or_(
            Job.submitted_by_user_id.is_(None),
            Job.submitted_by_user_id == user_id,
        )

    if settings.job_discovery_enable_test_provider:
        return ownership

    return and_(ownership, Job.source.notin_(NON_PRODUCTION_SOURCES))


def get_visible_job(
    db: Session, *, job_id: UUID, user_id: UUID
) -> Job | None:
    """The job, or None when it does not exist *or* is another user's
    private submission - callers must treat both the same way."""
    return (
        db.query(Job)
        .filter(Job.id == job_id, visible_jobs_filter(user_id))
        .first()
    )


def active_jobs_filter(now: datetime | None = None):
    """SQL filter for jobs that are still open: `is_active`, and not past
    the provider-stated `expires_at` (AJI-028).

    Evaluated at query time, so a job disappears the moment its stated
    expiry passes - no sweep job, no write. A NULL `expires_at` means the
    provider stated no expiry and the job stays open: a posting is never
    treated as closed because a discovery run did not see it.

    `now` is naive UTC (the `jobs` timestamp convention); it defaults to
    the current time and exists for deterministic tests.
    """
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    elif now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)

    return and_(
        Job.is_active.is_(True),
        or_(Job.expires_at.is_(None), Job.expires_at > now),
    )
