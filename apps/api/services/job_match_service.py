"""Job Match orchestration service.

This is the database-touching orchestration layer between the /jobs
router and the pure, DB-free services.job_matching engine (which
computes a deterministic Job Match Score but never accesses the
database). See services/job_matching/service.py's own docstring for that
boundary.

Job-side requirements (AJI-014 reconciliation): job requirements come
from AJI-012's persisted `JobIntelligence` snapshot (via
apps.api.services.job_intelligence.service), never from re-parsing raw
JD text here. If no snapshot exists yet for the job, one is generated on
demand (idempotent/cached — the same function the
/jobs/{job_id}/intelligence endpoint and apps.api.services.
ats_alignment_service already call). This replaces the previous
implementation, which ran its own text-splitting/skill-extraction
directly over raw `Job.description`/`requirements`/`responsibilities`
text (services.job_matching.extractor), duplicating what AJI-012 already
does more thoroughly (clause-level required-vs-preferred classification
rather than a single whole-text split point, and correctly excluding
`responsibilities` from requirements — see docs/ARCHITECTURE.md). The
downstream scoring engine (services.job_matching.matcher/scorer) is
unchanged: only the source of `JobRequirements` changed.

Job Match vs. ATS Alignment vs. Hard Eligibility: these stay three
separate, independently-computed artifacts, never merged into one score
or table (docs/ARCHITECTURE.md). Job Match does not consult
`AtsAlignmentResult` or `JobEligibilityResult` here — a job's Hard
Eligibility status is enforced by the separate /jobs/{job_id}/eligibility
pre-filter, not by this scoring path (an ineligible job still gets a Job
Match score, exactly as before AJI-014).

Idempotency: calculate_job_match() is keyed on (user_id, job_id,
resume_version_id, job_intelligence_id, engine_version), mirroring
apps.api.services.ats_alignment_service. A cache hit returns the
existing row unchanged; a changed resume version, a new Job Intelligence
snapshot, or a bumped engine version always produces a new, additional
row. See JobMatchResult's docstring (apps/api/models.py).

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
from apps.api.services.job_intelligence.contracts import JobIntelligenceResult
from apps.api.services.job_intelligence.service import (
    JobIntelligenceServiceError,
    generate_job_intelligence,
    get_latest_job_intelligence,
)
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from services.job_matching.contracts import (
    ExperienceRequirement as JobMatchExperienceRequirement,
)
from services.job_matching.contracts import JobRequirements
from services.job_matching.resume_adapter import (
    build_resume_evidence_from_analysis,
)
from services.job_matching.scorer import ENGINE_VERSION
from services.job_matching.service import JobMatchingService


class JobMatchServiceError(RuntimeError):
    """Application-level error for Job Match orchestration failures."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def get_latest_job_match(
    db: Session,
    *,
    user_id: UUID,
    job_id: UUID,
    resume_version_id: UUID | None = None,
) -> JobMatchResult | None:
    """
    Read-only lookup of the newest Job Match result for this user and job
    (optionally pinned to one exact resume version), mirroring
    `ats_alignment_service.get_latest_ats_alignment`. Never recomputes and
    never generates Job Intelligence, so reading can't trigger an AI call.
    """
    query = db.query(JobMatchResult).filter(
        JobMatchResult.user_id == user_id,
        JobMatchResult.job_id == job_id,
    )

    if resume_version_id is not None:
        query = query.filter(JobMatchResult.resume_version_id == resume_version_id)

    return query.order_by(JobMatchResult.created_at.desc()).first()


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


# ---------------------------------------------------------------------------
# Job Intelligence -> Job Match requirement mapping
# ---------------------------------------------------------------------------


def _build_job_requirements(
    intelligence: JobIntelligenceResult,
) -> JobRequirements:
    """
    Map an AJI-012 JobIntelligenceResult into the JobRequirements shape
    services.job_matching's scoring engine consumes.

    Mirrors apps.api.services.ats_alignment_service's own
    JobIntelligence -> requirement mapping (kept as a separate, smaller
    copy here since Job Match's JobRequirements shape only carries
    skills/experience, unlike ATS Alignment's flat requirement-item list,
    which also covers education/certifications that Job Match's existing
    scoring components never used). AJI-012's `required`/`preferred`
    two-tier taxonomy maps 1:1 onto `must_have_skills`/`preferred_skills`
    (and the matching experience lists) — no third tier is introduced.
    """
    return JobRequirements(
        must_have_skills=[
            skill.canonical_skill for skill in intelligence.required_skills
        ],
        preferred_skills=[
            skill.canonical_skill for skill in intelligence.preferred_skills
        ],
        must_have_experience=[
            JobMatchExperienceRequirement(
                minimum_years=experience.minimum_years,
                maximum_years=experience.maximum_years,
                description=experience.evidence_text,
            )
            for experience in intelligence.required_experience
        ],
        preferred_experience=[
            JobMatchExperienceRequirement(
                minimum_years=experience.minimum_years,
                maximum_years=experience.maximum_years,
                description=experience.evidence_text,
            )
            for experience in intelligence.preferred_experience
        ],
    )


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

    job_intelligence_row = get_latest_job_intelligence(db, job_id=job_id)

    if job_intelligence_row is None:
        try:
            job_intelligence_row = generate_job_intelligence(db, job_id=job_id)
        except JobIntelligenceServiceError as exc:
            raise JobMatchServiceError(
                "Unable to obtain Job Intelligence for this job.",
                status_code=exc.status_code,
            ) from exc

    cached = (
        db.query(JobMatchResult)
        .filter(
            JobMatchResult.user_id == current_user.id,
            JobMatchResult.job_id == job_id,
            JobMatchResult.resume_version_id == resume_version.id,
            JobMatchResult.job_intelligence_id == job_intelligence_row.id,
            JobMatchResult.engine_version == ENGINE_VERSION,
        )
        .order_by(JobMatchResult.created_at.desc())
        .first()
    )

    if cached is not None:
        return cached

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

    intelligence = JobIntelligenceResult.model_validate(
        job_intelligence_row.structured_intelligence
    )

    job_requirements = _build_job_requirements(intelligence)

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
        job_intelligence_id=job_intelligence_row.id,
        job_content_fingerprint=job_intelligence_row.content_fingerprint,
        engine_version=result.engine_version,
        score=result.score,
        confidence=result.confidence,
        result=result_data,
    )

    db.add(match_record)
    db.commit()
    db.refresh(match_record)

    return match_record
