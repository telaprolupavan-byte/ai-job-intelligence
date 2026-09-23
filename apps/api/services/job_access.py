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
rows exist in a database that later has test mode turned off.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import Job
from services.job_discovery.sources.test_fixture import TEST_FIXTURE_SOURCE


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

    return and_(ownership, Job.source != TEST_FIXTURE_SOURCE)


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
