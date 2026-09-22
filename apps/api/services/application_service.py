"""Application Tracking orchestration service.

NERO never auto-applies: this module only ever records that a user saved
a job or told NERO they applied/heard back somewhere else. Every status
change is both written onto the current `SavedJob` row and appended to
`ApplicationStatusEvent` as permanent history, so the Application Detail
view can show a real timeline rather than only the current status.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from apps.api.models import ApplicationStatusEvent, SavedJob, User
from apps.api.schemas import APPLICATION_STATUSES
from apps.api.services.job_access import get_visible_job


class ApplicationServiceError(Exception):
    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class ApplicationNotFoundError(ApplicationServiceError):
    def __init__(self) -> None:
        super().__init__("Application not found.", status_code=404)


class JobNotFoundError(ApplicationServiceError):
    def __init__(self) -> None:
        super().__init__("Job not found.", status_code=404)


def _record_status_event(db: Session, saved_job: SavedJob, status: str) -> None:
    db.add(
        ApplicationStatusEvent(
            saved_job_id=saved_job.id,
            status=status,
        )
    )


def create_application(
    db: Session,
    *,
    current_user: User,
    job_id: str,
) -> SavedJob:
    """Save a job for tracking. Idempotent: re-saving a job the user
    already tracks returns the existing record unchanged rather than
    erroring or creating a duplicate row (the DB-level unique constraint
    on (user_id, job_id) is the hard guarantee behind this)."""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise JobNotFoundError()

    # AJI-022: another user's private submitted job is "not found" too.
    job = get_visible_job(db, job_id=job_uuid, user_id=current_user.id)

    if job is None:
        raise JobNotFoundError()

    existing = (
        db.query(SavedJob)
        .filter(
            SavedJob.user_id == current_user.id,
            SavedJob.job_id == job_uuid,
        )
        .first()
    )

    if existing is not None:
        return existing

    saved_job = SavedJob(
        user_id=current_user.id,
        job_id=job_uuid,
        status="saved",
    )
    db.add(saved_job)
    db.flush()

    _record_status_event(db, saved_job, "saved")

    db.commit()
    db.refresh(saved_job)

    return saved_job


def list_applications(db: Session, *, current_user: User) -> list[SavedJob]:
    return (
        db.query(SavedJob)
        .options(joinedload(SavedJob.job))
        .filter(SavedJob.user_id == current_user.id)
        .order_by(SavedJob.updated_at.desc())
        .all()
    )


def get_application(
    db: Session,
    *,
    current_user: User,
    application_id: str,
) -> SavedJob:
    try:
        application_uuid = UUID(application_id)
    except ValueError:
        raise ApplicationNotFoundError()

    application = (
        db.query(SavedJob)
        .options(
            joinedload(SavedJob.job),
            joinedload(SavedJob.status_events),
        )
        .filter(
            SavedJob.id == application_uuid,
            SavedJob.user_id == current_user.id,
        )
        .first()
    )

    if application is None:
        raise ApplicationNotFoundError()

    return application


def remove_saved_job(
    db: Session,
    *,
    current_user: User,
    application_id: str,
) -> None:
    """Remove a saved-but-not-yet-applied job from tracking.

    Only valid while status is still "saved" - once the user has marked
    it applied, the row is an Application and its history must be kept
    (see module docstring); withdrawing via status update is the correct
    action at that point, not deletion.
    """
    application = get_application(
        db, current_user=current_user, application_id=application_id
    )

    if application.status != "saved":
        raise ApplicationServiceError(
            "Cannot remove an application that has already been applied "
            "to. Update its status (e.g. withdrawn) instead.",
            status_code=409,
        )

    db.delete(application)
    db.commit()


def update_application_status(
    db: Session,
    *,
    current_user: User,
    application_id: str,
    status: str,
) -> SavedJob:
    if status not in APPLICATION_STATUSES:
        raise ApplicationServiceError(
            f"Invalid status: {status}", status_code=422
        )

    application = get_application(
        db, current_user=current_user, application_id=application_id
    )

    application.status = status
    application.updated_at = datetime.utcnow()

    if status == "applied" and application.applied_at is None:
        application.applied_at = datetime.utcnow()

    _record_status_event(db, application, status)

    db.commit()
    db.refresh(application)

    return application


def count_active_applications(db: Session, *, current_user: User) -> int:
    """"Active" means the user is still pursuing this job: applied or
    further along, but not a terminal outcome (rejected/withdrawn), and
    not merely saved-but-not-yet-applied."""
    return (
        db.query(SavedJob)
        .filter(
            SavedJob.user_id == current_user.id,
            SavedJob.status.in_(["applied", "interviewing", "offer"]),
        )
        .count()
    )
