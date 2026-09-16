from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import Resume, User

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

    return {
        "user": {
            "email": current_user.email,
        },
        "resume": {
            "status": resume_status,
            "name": resume_name,
        },
        "ats": {
            "score": None,
            "status": "not_available",
        },
        "jobs": {
            "available": False,
        },
        "applications": {
            "available": False,
        },
    }