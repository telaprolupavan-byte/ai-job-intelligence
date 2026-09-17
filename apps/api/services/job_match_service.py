"""Job Match orchestration service.

This is the database-touching orchestration layer between the /jobs
router and the pure, DB-free services.job_matching engine (which
computes a deterministic Job Match Score but never accesses the
database). See services/job_matching/service.py's own docstring for that
boundary.

Resume version selection:

calculate_job_match() accepts an optional explicit resume_version_id so
future callers (e.g. an eventual Resume Version Selection UI) can pin the
match to an exact ResumeVersion. Ownership of that ResumeVersion is
always enforced (it must belong to the requesting user). When no
resume_version_id is supplied, the existing default behavior is
preserved unchanged: the user's most recently created Resume, preferring
its master ResumeVersion and falling back to its newest version.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.models import Job, JobMatchResult, Resume, ResumeVersion, User
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from services.job_matching.extractor import (
    build_job_requirements,
    split_preferred_section,
)
from services.job_matching.resume_adapter import (
    build_resume_evidence_from_analysis,
)
from services.job_matching.service import JobMatchingService


class JobMatchServiceError(RuntimeError):
    """Application-level error for Job Match orchestration failures."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def _resolve_resume_version(
    db: Session,
    *,
    current_user: User,
    resume_version_id: UUID | None,
) -> ResumeVersion:
    """
    Resolve the exact ResumeVersion to use for a Job Match calculation.

    When resume_version_id is given, it must belong to current_user
    (ownership enforced); otherwise the caller receives the same "not
    found" error as any other unowned/nonexistent resource in this API,
    so a user can never distinguish "belongs to someone else" from
    "does not exist" for another user's data.
    """
    if resume_version_id is not None:
        resume_version = (
            db.query(ResumeVersion)
            .join(ResumeVersion.resume)
            .filter(
                ResumeVersion.id == resume_version_id,
                Resume.user_id == current_user.id,
            )
            .first()
        )

        if resume_version is None:
            raise JobMatchServiceError(
                "Resume version not found.",
                status_code=404,
            )

        return resume_version

    # Default behavior (unchanged): the user's most recent Resume,
    # preferring its master ResumeVersion, falling back to its newest.
    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )

    if resume is None:
        raise JobMatchServiceError(
            "No resume found for this user",
            status_code=404,
        )

    resume_version = (
        db.query(ResumeVersion)
        .filter(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.is_master.is_(True),
        )
        .order_by(ResumeVersion.created_at.desc())
        .first()
    )

    if resume_version is None:
        resume_version = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.resume_id == resume.id)
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )

    if resume_version is None:
        raise JobMatchServiceError(
            "No resume version found for this user",
            status_code=404,
        )

    return resume_version


def calculate_job_match(
    *,
    db: Session,
    current_user: User,
    job_id: UUID,
    resume_version_id: UUID | None = None,
) -> JobMatchResult:
    """
    Calculate and persist a deterministic Job Match Score for the
    authenticated user against a specific job, using an explicit
    ResumeVersion when provided, or the existing default selection
    otherwise.
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if job is None:
        raise JobMatchServiceError("Job not found", status_code=404)

    resume_version = _resolve_resume_version(
        db,
        current_user=current_user,
        resume_version_id=resume_version_id,
    )

    analysis = analyze_resume_deterministically(
        resume_version.content_text
    )

    profile = current_user.profile

    resume_evidence = build_resume_evidence_from_analysis(
        analysis,
        experience_years=(
            profile.years_experience if profile else None
        ),
    )

    resume_titles = (
        profile.target_titles
        if profile and profile.target_titles
        else []
    )

    requirement_text = "\n".join(
        part
        for part in [
            job.requirements,
            job.responsibilities,
            job.description,
        ]
        if part
    )

    must_have_text, preferred_text = split_preferred_section(
        requirement_text
    )

    job_requirements = build_job_requirements(
        must_have_text=must_have_text,
        preferred_text=preferred_text,
    )

    preferences = current_user.preferences

    preferred_remote_type = (
        preferences.remote_preference if preferences else None
    )

    preferred_location = None

    if preferences and preferences.locations:
        preferred_location = preferences.locations[0]

    preferred_employment_type = None

    if preferences and preferences.employment_types:
        preferred_employment_type = preferences.employment_types[0]

    service = JobMatchingService()

    result = service.calculate_match(
        job_title=job.title,
        job_requirements=job_requirements,
        resume_evidence=resume_evidence,
        resume_titles=resume_titles,
        job_remote_type=job.remote_type,
        job_location=job.location,
        job_employment_type=job.employment_type,
        preferred_remote_type=preferred_remote_type,
        preferred_location=preferred_location,
        preferred_employment_type=preferred_employment_type,
    )

    result_data = {
        "score": result.score,
        "confidence": result.confidence,
        "must_have_matches": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.must_have_matches
        ],
        "must_have_gaps": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.must_have_gaps
        ],
        "preferred_matches": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.preferred_matches
        ],
        "preferred_gaps": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.preferred_gaps
        ],
        "components": [
            {
                "name": component.name,
                "score": component.score,
                "max_score": component.max_score,
                "explanation": component.explanation,
            }
            for component in result.components
        ],
        "strengths": result.strengths,
        "skill_gaps": result.skill_gaps,
    }

    match_record = JobMatchResult(
        user_id=current_user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        engine_version=result.engine_version,
        score=result.score,
        confidence=result.confidence,
        result=result_data,
    )

    db.add(match_record)
    db.commit()
    db.refresh(match_record)

    return match_record
