from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import Resume, ResumeAnalysis, ResumeVersion, User

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

    ats_score = None
    ats_status = "not_checked"

    if resume:
        latest_version = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.resume_id == resume.id)
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )

        if latest_version:
            analysis = (
                db.query(ResumeAnalysis)
                .filter(ResumeAnalysis.resume_version_id == latest_version.id)
                .order_by(ResumeAnalysis.created_at.desc())
                .first()
            )

            if analysis:
                ats_score = analysis.ats_score

                if ats_score is not None:
                    ats_status = "pass" if ats_score >= 80 else "needs_improvement"

    return {
        "user": {
            "email": current_user.email,
        },
        "resume": {
            "status": resume_status,
            "name": resume_name,
        },
        "ats": {
            "score": ats_score,
            "status": ats_status,
        },
        "jobs": {
            "new": 0,
            "full_time": 0,
            "contract": 0,
        },
        "applications": {
            "applied": 0,
            "in_review": 0,
            "interview": 0,
            "offers": 0,
        },
    }