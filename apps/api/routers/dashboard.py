"""Dashboard aggregate read (UI-DASH-001).

Every field here is read from an artifact that already exists elsewhere
in the pipeline (see docs/ARCHITECTURE.md) — this router never computes
or triggers new analysis, it only summarizes the current state for the
authenticated user:

- `resume` / `validation` — the user's most recent `Resume` and whether
  any of its versions has a `ResumeAIAnalysis` (the same "has_analysis"
  signal already surfaced per-version by `GET /resumes/{id}/versions`).
- `ats` — the user's most recent `AtsAlignmentResult` across any job
  (AJI-013). There is no single job-independent "ATS score"; this is
  the most recent check the user has actually run, wherever it was run.
- `jobs` — real counts from the `Job` table (AJI has no per-user job
  personalization on this surface, so these are global counts).
- `applications` — real counts from the user's own `SavedJob` rows
  (Application Tracking; see apps/api/services/application_service.py).
  `active_count` is applications in "applied"/"interviewing"/"offer" -
  a merely-saved-but-not-yet-applied job is not counted as active.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import (
    AtsAlignmentResult,
    Company,
    Job,
    Resume,
    ResumeAIAnalysis,
    User,
)
from apps.api.services.application_service import count_active_applications
from apps.api.services.job_access import visible_jobs_filter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Mirrors the "80% target" already surfaced in the existing ATS Readiness
# copy — not a new product decision, just reused as the pass/fail split
# for the dashboard's compact status pill.
ATS_PASS_THRESHOLD = 80

RECENT_JOBS_LIMIT = 4


def _as_utc(timestamp: datetime) -> datetime:
    """Normalize to a timezone-aware UTC datetime so timestamps from
    naive columns (e.g. `ResumeAIAnalysis.created_at`) and aware columns
    (e.g. `AtsAlignmentResult.created_at`) can be compared/ordered."""
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)

    return timestamp.astimezone(timezone.utc)


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

    latest_analysis = None

    if resume is not None:
        version_ids = [version.id for version in resume.versions]

        if version_ids:
            latest_analysis = (
                db.query(ResumeAIAnalysis)
                .filter(ResumeAIAnalysis.resume_version_id.in_(version_ids))
                .order_by(ResumeAIAnalysis.created_at.desc())
                .first()
            )

    latest_ats = (
        db.query(AtsAlignmentResult)
        .filter(AtsAlignmentResult.user_id == current_user.id)
        .order_by(AtsAlignmentResult.created_at.desc())
        .first()
    )

    if latest_ats is not None:
        ats_score = round(latest_ats.overall_score)
        ats_status = (
            "pass" if ats_score >= ATS_PASS_THRESHOLD else "needs_improvement"
        )
    else:
        ats_score = None
        ats_status = "not_checked"

    checked_at_candidates = [
        _as_utc(timestamp)
        for timestamp in (
            latest_analysis.created_at if latest_analysis else None,
            latest_ats.created_at if latest_ats else None,
        )
        if timestamp is not None
    ]
    last_checked_at = max(checked_at_candidates) if checked_at_candidates else None

    today = datetime.utcnow().date()

    # AJI-022: discovered jobs plus this user's own submissions only.
    visible = visible_jobs_filter(current_user.id)

    active_jobs = db.query(Job).filter(Job.is_active.is_(True), visible)

    jobs_today_count = active_jobs.filter(
        func.date(Job.first_seen_at) == today
    ).count()

    full_time_count = active_jobs.filter(
        Job.employment_type == "full_time"
    ).count()

    contract_count = active_jobs.filter(
        Job.employment_type == "contract"
    ).count()

    recent_rows = (
        db.query(Job, Company.name)
        .outerjoin(Company, Job.company_id == Company.id)
        .filter(Job.is_active.is_(True), visible)
        .order_by(Job.first_seen_at.desc())
        .limit(RECENT_JOBS_LIMIT)
        .all()
    )

    recent_jobs = [
        {
            "id": str(job.id),
            "title": job.title,
            "company": company_name,
            "location": job.location,
            "employment_type": job.employment_type,
            "remote_type": job.remote_type,
        }
        for job, company_name in recent_rows
    ]

    return {
        "user": {
            "email": current_user.email,
        },
        "resume": {
            "status": resume_status,
            "name": resume_name,
        },
        "validation": {
            "status": "analyzed" if latest_analysis is not None else "pending",
        },
        "ats": {
            "score": ats_score,
            "status": ats_status,
        },
        "last_checked_at": (
            last_checked_at.isoformat() if last_checked_at else None
        ),
        "jobs": {
            "available": True,
            "today_count": jobs_today_count,
            "full_time_count": full_time_count,
            "contract_count": contract_count,
            "recent": recent_jobs,
        },
        "applications": {
            "available": True,
            "active_count": count_active_applications(
                db, current_user=current_user
            ),
        },
    }
