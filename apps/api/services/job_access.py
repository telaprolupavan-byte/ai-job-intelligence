"""Job visibility / ownership rules (AJI-022).

A `Job` is either discovered (`submitted_by_user_id IS NULL`, shared with
every user - the only kind that existed before AJI-022) or user-submitted
(private to the user whose id is in that column). Every per-job read or
write goes through `visible_jobs_filter()`/`get_visible_job()` so this
rule lives in exactly one place.

A job the caller cannot see is reported exactly like a job that does not
exist (a plain 404 "Job not found"), so another user's private job id is
never confirmed to exist.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from apps.api.models import Job


def visible_jobs_filter(user_id: UUID | None):
    """SQL filter for the jobs `user_id` may see.

    `None` (an anonymous caller) sees discovered jobs only.
    """
    if user_id is None:
        return Job.submitted_by_user_id.is_(None)

    return or_(
        Job.submitted_by_user_id.is_(None),
        Job.submitted_by_user_id == user_id,
    )


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
