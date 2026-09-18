"""ATS Alignment orchestration service (AJI-013).

The database-touching layer between the /jobs router and the pure,
DB-free services.ats_alignment engine — the same DB/pure-core split
apps.api.services.job_match_service uses for Job Match and
apps.api.services.job_intelligence.service uses for Job Intelligence.

Source data (AJI-013 section 5, reused rather than recreated):

- Job-side requirements come from AJI-012's persisted `JobIntelligence`
  snapshot (via apps.api.services.job_intelligence.service), never
  re-parsed from raw JD text here. If no snapshot exists yet for the
  job, one is generated on demand (idempotent/cached — the same
  function the /jobs/{job_id}/intelligence endpoint calls), since ATS
  Alignment cannot answer its question without it.
- Resume-side evidence comes from the existing deterministic resume
  analyzer (apps.api.services.resume_ai.deterministic), the same
  function Job Match already reuses, plus the user's declared
  `Profile.years_experience`. No second resume parser is introduced.

Versioning/idempotency: an ATS Alignment result is keyed by
(user_id, job_id, resume_version_id, job_intelligence_id,
engine_version). Resume content is immutable per `ResumeVersion`, and a
`JobIntelligence` row is itself an immutable, insert-only snapshot, so a
cached result for this exact combination is valid indefinitely — reused
exactly like `ResumeAIAnalysis`/`JobIntelligence` caching. A changed
resume version, a new Job Intelligence snapshot (edited JD or bumped
AJI-012 pipeline version), or a bumped ATS `engine_version` always
produces a new, additional row; existing rows are never overwritten
(AJI-013 section 12).

User isolation (AJI-013 section 14): every read/write here is always
scoped to the requesting user's own `user_id` — never derived from
`job_id`/`resume_version_id` alone.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.models import (
    AtsAlignmentResult,
    Job,
    JobIntelligence,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services.job_intelligence.contracts import JobIntelligenceResult
from apps.api.services.job_intelligence.service import (
    JobIntelligenceServiceError,
    generate_job_intelligence,
    get_latest_job_intelligence,
)
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from services.ats_alignment.contracts import JobRequirementItem
from services.ats_alignment.engine import ENGINE_VERSION, evaluate_ats_alignment
from services.ats_alignment.resume_adapter import build_resume_evidence_profile


class ATSAlignmentServiceError(RuntimeError):
    """Application-level error for ATS Alignment orchestration failures."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Resume version resolution
# ---------------------------------------------------------------------------

def _resolve_resume_version(
    db: Session,
    *,
    current_user: User,
    resume_version_id: UUID | None,
) -> ResumeVersion:
    """
    Resolve the exact ResumeVersion to use for an ATS Alignment
    calculation. Mirrors
    apps.api.services.job_match_service._resolve_resume_version exactly
    (same ownership-enforcement and default-selection behavior), kept as
    its own copy rather than a shared import since neither existing
    orchestration service currently exposes this as a public helper.
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
            raise ATSAlignmentServiceError(
                "Resume version not found.",
                status_code=404,
            )

        return resume_version

    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )

    if resume is None:
        raise ATSAlignmentServiceError(
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
        raise ATSAlignmentServiceError(
            "No resume version found for this user",
            status_code=404,
        )

    return resume_version


# ---------------------------------------------------------------------------
# Job Intelligence -> ATS requirement mapping
# ---------------------------------------------------------------------------

_LEVEL_TO_CATEGORY = {
    "required": "must_have",
    "preferred": "preferred",
}


def _build_job_requirements(
    intelligence: JobIntelligenceResult,
) -> list[JobRequirementItem]:
    """
    Map an AJI-012 JobIntelligenceResult into the flat, independently-
    evaluable requirement list the ATS engine consumes.

    Category taxonomy: AJI-012's `Level` ("required"/"preferred") maps
    1:1 onto ATS Alignment's `RequirementCategory`
    ("must_have"/"preferred") — see
    services/ats_alignment/contracts.py's module docstring for why a
    third "nice_to_have" tier is not introduced here.
    """
    items: list[JobRequirementItem] = []

    for skill in [*intelligence.required_skills, *intelligence.preferred_skills]:
        items.append(
            JobRequirementItem(
                requirement_id=f"skill:{skill.canonical_skill}",
                requirement_type="skill",
                category=_LEVEL_TO_CATEGORY[skill.level],
                requirement_text=skill.canonical_skill,
                jd_evidence=skill.evidence_text,
                canonical_skill=skill.canonical_skill,
            )
        )

    for index, experience in enumerate(
        [*intelligence.required_experience, *intelligence.preferred_experience]
    ):
        if experience.minimum_years is None:
            # Nothing objectively comparable without a minimum-years
            # figure; skip rather than manufacture an unverifiable result.
            continue

        label = f"{experience.minimum_years:g}+ years"
        if experience.area:
            label += f" of {experience.area}"

        items.append(
            JobRequirementItem(
                requirement_id=f"experience:{index}:{experience.area or 'general'}",
                requirement_type="experience",
                category=_LEVEL_TO_CATEGORY[experience.level],
                requirement_text=label,
                jd_evidence=experience.evidence_text,
                minimum_years=experience.minimum_years,
                area=experience.area,
            )
        )

    for index, education in enumerate(intelligence.education):
        label = education.degree_level or "Degree"
        if education.field_of_study:
            label += f" in {education.field_of_study}"

        items.append(
            JobRequirementItem(
                requirement_id=f"education:{index}",
                requirement_type="education",
                category=_LEVEL_TO_CATEGORY[education.level],
                requirement_text=label,
                jd_evidence=education.evidence_text,
                degree_level=education.degree_level,
                field_of_study=education.field_of_study,
            )
        )

    for index, certification in enumerate(intelligence.certifications):
        items.append(
            JobRequirementItem(
                requirement_id=f"certification:{index}",
                requirement_type="certification",
                category=_LEVEL_TO_CATEGORY[certification.level],
                requirement_text=certification.name,
                jd_evidence=certification.evidence_text,
                certification_name=certification.name,
            )
        )

    return items


# ---------------------------------------------------------------------------
# Read (never computes)
# ---------------------------------------------------------------------------

def get_latest_ats_alignment(
    db: Session,
    *,
    user_id: UUID,
    job_id: UUID,
    resume_version_id: UUID | None = None,
) -> AtsAlignmentResult | None:
    """
    Read-only lookup of the newest ATS Alignment result for this user and
    job (optionally pinned to one exact resume version). Never recomputes
    or calls generate_job_intelligence.
    """
    query = db.query(AtsAlignmentResult).filter(
        AtsAlignmentResult.user_id == user_id,
        AtsAlignmentResult.job_id == job_id,
    )

    if resume_version_id is not None:
        query = query.filter(
            AtsAlignmentResult.resume_version_id == resume_version_id
        )

    return query.order_by(AtsAlignmentResult.created_at.desc()).first()


# ---------------------------------------------------------------------------
# Create-or-reuse
# ---------------------------------------------------------------------------

def calculate_ats_alignment(
    *,
    db: Session,
    current_user: User,
    job_id: UUID,
    resume_version_id: UUID | None = None,
) -> AtsAlignmentResult:
    job = db.query(Job).filter(Job.id == job_id).first()

    if job is None:
        raise ATSAlignmentServiceError("Job not found", status_code=404)

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
            raise ATSAlignmentServiceError(
                "Unable to obtain Job Intelligence for this job.",
                status_code=exc.status_code,
            ) from exc

    cached = (
        db.query(AtsAlignmentResult)
        .filter(
            AtsAlignmentResult.user_id == current_user.id,
            AtsAlignmentResult.job_id == job_id,
            AtsAlignmentResult.resume_version_id == resume_version.id,
            AtsAlignmentResult.job_intelligence_id == job_intelligence_row.id,
            AtsAlignmentResult.engine_version == ENGINE_VERSION,
        )
        .order_by(AtsAlignmentResult.created_at.desc())
        .first()
    )

    if cached is not None:
        return cached

    intelligence = JobIntelligenceResult.model_validate(
        job_intelligence_row.structured_intelligence
    )
    job_requirements = _build_job_requirements(intelligence)

    resume_text = resume_version.content_text.strip()

    if not resume_text:
        raise ATSAlignmentServiceError(
            "Resume version contains no readable text.",
            status_code=422,
        )

    deterministic_analysis = analyze_resume_deterministically(resume_text)

    profile = current_user.profile

    resume_profile = build_resume_evidence_profile(
        deterministic_analysis,
        raw_text=resume_text,
        years_experience=profile.years_experience if profile else None,
    )

    result = evaluate_ats_alignment(job_requirements, resume_profile)

    if result is None:
        raise ATSAlignmentServiceError(
            "Job Intelligence for this job contains no analyzable "
            "requirements.",
            status_code=422,
        )

    result_data = {
        "must_have_total": result.must_have_total,
        "must_have_matched": result.must_have_matched,
        "preferred_total": result.preferred_total,
        "preferred_matched": result.preferred_matched,
        "scoring_version": result.scoring_version,
        "must_have_ceiling": result.must_have_ceiling,
        "score_components": [
            {
                "name": component.name,
                "weight": component.weight,
                "score": component.score,
                "weighted_score": component.weighted_score,
                "explanation": component.explanation,
            }
            for component in result.components
        ],
        "requirement_results": [
            {
                "requirement_id": item.requirement_id,
                "requirement_type": item.requirement_type,
                "category": item.category,
                "requirement_text": item.requirement_text,
                "status": item.status,
                "jd_evidence": item.jd_evidence,
                "resume_evidence": item.resume_evidence,
                "explanation": item.explanation,
                "confidence": item.confidence,
            }
            for item in result.requirement_results
        ],
    }

    record = AtsAlignmentResult(
        user_id=current_user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        job_intelligence_id=job_intelligence_row.id,
        job_content_fingerprint=job_intelligence_row.content_fingerprint,
        engine_version=result.engine_version,
        overall_score=result.overall_score,
        confidence=result.confidence,
        result=result_data,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
