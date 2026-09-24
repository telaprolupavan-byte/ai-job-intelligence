"""General Resume Intelligence API (AJI-027).

Job-independent: no route here takes a job, requirement or preference
parameter, and nothing here reads or writes ATS Alignment, Job Match,
Requirement Intelligence or Gap Analysis data. Errors use
`detail: {code, message}` (the AJI-021 convention) so the UI can branch
on a stable code.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import User
from apps.api.services.general_resume.contracts import (
    AssessmentRequest,
    ReviewRequest,
)
from apps.api.services.general_resume.service import (
    GeneralResumeServiceError,
    assess_resume_version,
    create_review,
    get_current_assessment,
    run_review_recheck,
    serialize_assessment,
    serialize_review,
)


router = APIRouter(
    prefix="/resumes",
    tags=["General Resume Intelligence"],
)


def _raise(exc: GeneralResumeServiceError):
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    ) from exc


@router.post("/versions/{resume_version_id}/general-assessment")
def create_general_assessment(
    resume_version_id: UUID,
    body: AssessmentRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compute the General Resume Score for this version, or return the
    existing assessment for the current pipeline."""
    try:
        assessment = assess_resume_version(
            db,
            user_id=current_user.id,
            resume_version_id=resume_version_id,
        )

        return serialize_assessment(
            db, user_id=current_user.id, assessment=assessment
        )
    except GeneralResumeServiceError as exc:
        _raise(exc)


@router.get("/versions/{resume_version_id}/general-assessment")
def read_general_assessment(
    resume_version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The latest assessment and computed readiness. Never computes and
    never calls an AI provider."""
    try:
        assessment = get_current_assessment(
            db,
            user_id=current_user.id,
            resume_version_id=resume_version_id,
        )
    except GeneralResumeServiceError as exc:
        _raise(exc)

    if assessment is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "assessment_not_found",
                "message": "This resume version has not been assessed yet.",
            },
        )

    return serialize_assessment(db, user_id=current_user.id, assessment=assessment)


@router.post(
    "/versions/{resume_version_id}/general-assessment/{assessment_id}/review"
)
def submit_general_review(
    resume_version_id: UUID,
    assessment_id: UUID,
    body: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record approve/reject decisions. If anything was approved, create a
    new version from the user's own text and recheck it. A failed recheck
    is still a 200: the version was created and kept."""
    try:
        review = create_review(
            db,
            current_user=current_user,
            resume_version_id=resume_version_id,
            assessment_id=assessment_id,
            decisions=[d.model_dump() for d in body.decisions],
        )

        return serialize_review(db, user_id=current_user.id, review=review)
    except GeneralResumeServiceError as exc:
        _raise(exc)


@router.post("/general-reviews/{review_id}/recheck")
def retry_general_recheck(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        review = run_review_recheck(
            db, current_user=current_user, review_id=review_id
        )

        return serialize_review(db, user_id=current_user.id, review=review)
    except GeneralResumeServiceError as exc:
        _raise(exc)
