"""GET/POST /jobs/{job_id}/resume-improvement and its recheck: Resume
Improvement approval and recheck (AJI-021)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import ResumeImprovement, User
from apps.api.routers.jobs.common import (
    _get_visible_job_or_404,
    _parse_optional_resume_version_id,
)
from apps.api.services.resume_improvement.contracts import (
    ResumeImprovementRequest,
)
from apps.api.services.resume_improvement.service import (
    ResumeImprovementServiceError,
    create_resume_improvement,
    get_latest_resume_improvement,
    run_recheck,
)


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


def _resume_improvement_to_response(record: ResumeImprovement) -> dict:
    result_data = record.result

    return {
        "id": str(record.id),
        "job_id": str(record.job_id),
        "gap_analysis_id": str(record.gap_analysis_id),
        "baseline_ats_alignment_id": str(record.baseline_ats_alignment_id),
        "parent_resume_version_id": str(record.parent_resume_version_id),
        "child_resume_version_id": str(record.child_resume_version_id),
        "child_resume_version_name": result_data["child_resume_version_name"],
        "parent_resume_version_name": result_data.get(
            "parent_resume_version_name"
        ),
        "engine_version": record.engine_version,
        "approved_count": record.approved_count,
        "skipped_count": record.skipped_count,
        "recheck_status": record.recheck_status,
        "recheck_error": record.recheck_error,
        "recheck_ats_alignment_id": (
            str(record.recheck_ats_alignment_id)
            if record.recheck_ats_alignment_id
            else None
        ),
        "decisions": result_data["decisions"],
        # None whenever the recheck has not produced a result - the
        # created version is still reported in full above, since a failed
        # recheck never costs the user the version they approved.
        "comparison": result_data.get("comparison"),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@router.get("/{job_id}/resume-improvement")
def get_resume_improvement(
    job_id: str,
    resume_version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated user's most recent Resume Improvement
    Approval & Recheck record (AJI-021) for a job, without applying
    anything. 404s when the user has not approved any improvements for
    this job yet.

    This endpoint never creates a resume version, never re-runs Gap
    Analysis, and never calls the ATS engine - every one of those only
    ever happens from an explicit POST, because approval is the user's
    to give.

    The optional `resume_version_id` pins the lookup to improvements
    based on that exact parent version, mirroring the same parameter on
    /jobs/{job_id}/ats and /jobs/{job_id}/gap-analysis.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    parsed_resume_version_id = _parse_optional_resume_version_id(
        resume_version_id
    )

    record = get_latest_resume_improvement(
        db,
        user_id=current_user.id,
        job_id=job_uuid,
        parent_resume_version_id=parsed_resume_version_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="No approved resume improvements for this job yet.",
        )

    return _resume_improvement_to_response(record)


@router.post("/{job_id}/resume-improvement")
def create_job_resume_improvement(
    job_id: str,
    payload: ResumeImprovementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apply the user's explicitly approved Gap Analysis suggestions
    (AJI-021): create a new child ResumeVersion from the approved,
    user-authored content and recheck it against this same job.

    Nothing here is automatic. The request must name an existing Gap
    Analysis result belonging to this user and carry an explicit
    approve/skip decision per suggestion; at least one approval is
    required, every approval must carry the user's own wording, and an
    `ADD_IF_TRUE` suggestion is only applied when the user confirmed it
    is accurate. The suggestion type is always read from the stored Gap
    Analysis row, so relabelling a gap in the request body cannot bypass
    that confirmation.

    The original resume version is never modified: the result is a new,
    additional version whose `parent_version_id` points back at it.
    Re-submitting the same approvals returns the existing record instead
    of creating a second version.

    This endpoint does NOT run the recheck. It returns with
    `recheck_status = "pending"`; running the recheck against the same
    job is a separate, explicit user action - POST
    /jobs/{job_id}/resume-improvement/{id}/recheck. The created version
    is already committed here, so it stays persisted and recoverable
    even if the recheck is never run.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    try:
        gap_analysis_uuid = UUID(payload.gap_analysis_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Gap Analysis not found.",
        )

    try:
        record = create_resume_improvement(
            db=db,
            current_user=current_user,
            job_id=job_uuid,
            gap_analysis_id=gap_analysis_uuid,
            decisions=[
                decision.model_dump() for decision in payload.decisions
            ],
        )
    except ResumeImprovementServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return _resume_improvement_to_response(record)


@router.post("/{job_id}/resume-improvement/{improvement_id}/recheck")
def retry_resume_improvement_recheck(
    job_id: str,
    improvement_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run the recheck for an existing Resume Improvement record (AJI-021).

    This is both the initial "Run recheck" action after a version is
    created and the retry after a failure - one endpoint, because they
    do exactly the same thing. It rechecks the child version against the
    same job using the existing, unmodified ATS Alignment path.

    Never creates a resume version and never re-applies decisions - the
    version and the approvals are already durable. A record whose
    recheck already succeeded is returned unchanged rather than being
    re-scored, so the comparison the user was shown cannot silently
    change underneath them.
    """
    job = _get_visible_job_or_404(db, job_id, current_user)
    job_uuid = job.id

    try:
        improvement_uuid = UUID(improvement_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Resume improvement not found.",
        )

    try:
        record = run_recheck(
            db=db,
            current_user=current_user,
            job_id=job_uuid,
            improvement_id=improvement_uuid,
        )
    except ResumeImprovementServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return _resume_improvement_to_response(record)
