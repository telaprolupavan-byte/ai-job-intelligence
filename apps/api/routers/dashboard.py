from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import AtsAlignmentResult, Job, Resume, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )

    resume_status = "ready" if resume else "not_ready"
    resume_name = resume.filename if resume else None

    # The most recent ATS Alignment result across any job — AtsAlignmentResult
    # is always scored per (user, job, resume version), there is no
    # resume-level score, so "the dashboard's ATS score" is the latest one
    # this user has actually run.
    latest_ats = (
        db.query(AtsAlignmentResult)
        .filter(AtsAlignmentResult.user_id == current_user.id)
        .order_by(AtsAlignmentResult.created_at.desc())
        .first()
    )

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )

    todays_jobs_query = db.query(Job).filter(
        Job.is_active.is_(True), Job.first_seen_at >= today_start
    )

    jobs_discovered_today = todays_jobs_query.count()

    # Employment types actually present among today's real jobs — never a
    # static list of every type the system supports, so the dashboard never
    # shows a category tag for data that isn't there.
    today_employment_types = sorted(
        {
            employment_type
            for (employment_type,) in todays_jobs_query.with_entities(
                Job.employment_type
            ).all()
            if employment_type
        }
    )

    return {
        "user": {
            "email": current_user.email,
        },
        "resume": {
            "status": resume_status,
            "name": resume_name,
        },
        "ats": {
            "score": latest_ats.overall_score if latest_ats else None,
            "checked_at": (
                latest_ats.created_at.isoformat() if latest_ats else None
            ),
        },
        "jobs": {
            "today_count": jobs_discovered_today,
            "today_employment_types": today_employment_types,
        },
        "applications": {
            "available": False,
        },
    }