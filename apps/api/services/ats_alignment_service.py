"""ATS Alignment orchestration service (AJI-013, integrated with
Requirement Intelligence by AJI-020C).

The database-touching layer between the /jobs router and the pure,
DB-free services.ats_alignment engine — the same DB/pure-core split
apps.api.services.job_match_service uses for Job Match and
apps.api.services.job_intelligence.service uses for Job Intelligence.

Source data (AJI-020C core integration rule):

- Job-side requirements come from AJI-020A/B's persisted
  `RequirementIntelligence` snapshot (via apps.api.services.
  requirement_intelligence.persistence_service), never re-parsed from
  raw JD text, and never re-derived from `JobIntelligence` either — see
  `_build_job_requirements_from_requirement_intelligence` below. If no
  snapshot exists yet for this (user, job), one is generated on demand
  (idempotent/cached — the same function
  `/jobs/{job_id}/requirement-intelligence` uses), since ATS Alignment
  cannot answer its question without it.
- `JobIntelligence` (AJI-012) is still generated/fetched here too, but
  purely to keep populating the existing `job_intelligence_id`/
  `job_content_fingerprint` lineage columns unchanged for backward
  compatibility — its *content* is no longer read to build the scored
  requirement list. See docs/ARCHITECTURE.md's AJI-020C section for why
  this column is retained rather than removed.
- Resume-side evidence comes from the existing deterministic resume
  analyzer (apps.api.services.resume_ai.deterministic), the same
  function Job Match already reuses, plus the user's declared
  `Profile.years_experience`. No second resume parser is introduced.

Versioning/idempotency: an ATS Alignment result is keyed by
(user_id, job_id, resume_version_id, job_intelligence_id,
requirement_intelligence_id, engine_version) — AJI-020C adds
`requirement_intelligence_id` to the existing four-part key rather than
replacing any part of it (AJI-020C section 11: "inspect the existing
persistence identity before changing it"). Resume content is immutable
per `ResumeVersion`, and both `JobIntelligence` and `RequirementIntelligence`
rows are themselves immutable, insert-only snapshots, so a cached result
for this exact combination is valid indefinitely. A changed resume
version, a new Requirement Intelligence snapshot (edited JD or bumped
AJI-020A pipeline/model version), a new Job Intelligence snapshot, or a
bumped ATS `engine_version` always produces a new, additional row;
existing rows are never overwritten (AJI-013 section 12).

Fallback policy (AJI-020C section 10): there is no approved fallback to
raw-JD parsing if Requirement Intelligence is unavailable. The existing,
already-approved pattern for this exact situation is "hard fail, never
silently reinterpret the JD" — `JobIntelligence` generation failure
already propagates as an `ATSAlignmentServiceError` with the underlying
status code rather than falling back to anything; Requirement
Intelligence generation failure is handled identically, reusing that
same pattern rather than inventing a new one.

User isolation (AJI-013 section 14, unchanged by AJI-020C): every
read/write here is always scoped to the requesting user's own `user_id`
— never derived from `job_id`/`resume_version_id` alone. This includes
the Requirement Intelligence lookup, since AJI-020B made that table
per-user too.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.models import (
    AtsAlignmentResult,
    Job,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services.job_intelligence.service import (
    JobIntelligenceServiceError,
    generate_job_intelligence,
    get_latest_job_intelligence,
)
from apps.api.services.requirement_intelligence.contracts import (
    RequirementIntelligenceResult,
)
from apps.api.services.requirement_intelligence.persistence_service import (
    RequirementIntelligencePersistenceError,
    generate_requirement_intelligence,
    get_latest_requirement_intelligence,
)
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from services.ats_alignment.contracts import (
    JobRequirementItem,
    RequirementRelationshipGroup,
    ScreeningConstraintInfo,
)
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
# Requirement Intelligence -> ATS requirement mapping (AJI-020C)
# ---------------------------------------------------------------------------

_IMPORTANCE_TO_CATEGORY: dict[str, str] = {
    "required": "must_have",
    "preferred": "preferred",
}


def _build_job_requirements_from_requirement_intelligence(
    intelligence: RequirementIntelligenceResult,
) -> tuple[
    list[JobRequirementItem],
    list[RequirementRelationshipGroup],
    list[ScreeningConstraintInfo],
]:
    """
    Map AJI-020A/B's `RequirementIntelligenceResult` into the ATS
    engine's existing evidence-evaluation model (AJI-020C section 5).

    Category taxonomy: only `importance in {"required", "preferred"}`
    items are ever mapped into a scored `JobRequirementItem` — mapped
    1:1 onto ATS Alignment's existing `RequirementCategory`
    ("must_have"/"preferred"), exactly like AJI-012's own two-tier
    mapping before it (see services/ats_alignment/contracts.py's module
    docstring). `contextual`/`informational` items, and every
    `requirement_type == "responsibility"` item (which AJI-020A's own
    locked contract validator forbids from ever being `required`/
    `preferred` in the first place), are excluded — they are not
    requirements to score a candidate against by AJI-020A's own locked
    definition, so there is nothing to invent a category for.

    Relationships (AND/OR/MIN_COUNT/EQUIVALENT) and screening
    constraints are mapped separately and returned unevaluated — see
    `RequirementRelationshipGroup`/`ScreeningConstraintInfo` in
    contracts.py for why this function never folds them into a scored
    `JobRequirementItem` or any derived group-level verdict.
    """
    items: list[JobRequirementItem] = []

    for req in intelligence.requirements:
        category = _IMPORTANCE_TO_CATEGORY.get(req.importance)

        if category is None:
            continue

        canonical_skill = req.canonical_terms[0] if req.canonical_terms else None
        minimum_years: float | None = None
        area: str | None = None
        degree_level: str | None = None
        field_of_study: str | None = None
        certification_name: str | None = None

        if req.requirement_type == "skill":
            requirement_text = canonical_skill or req.statement
        elif req.requirement_type == "experience":
            minimum_years = req.experience.minimum_years if req.experience else None
            area = req.experience.area if req.experience else None
            requirement_text = (
                f"{minimum_years:g}+ years" if minimum_years is not None else "Experience"
            ) + (f" of {area}" if area else "")
        elif req.requirement_type == "education":
            degree_level = req.education.degree_level if req.education else None
            field_of_study = req.education.field_of_study if req.education else None
            requirement_text = (degree_level or "Degree") + (
                f" in {field_of_study}" if field_of_study else ""
            )
        elif req.requirement_type == "certification":
            certification_name = (
                req.certification.name if req.certification else req.statement
            )
            requirement_text = certification_name
        else:
            # "responsibility" - unreachable in practice (never
            # required/preferred - see the docstring above) but guarded
            # defensively rather than assumed.
            continue

        items.append(
            JobRequirementItem(
                requirement_id=req.id,
                requirement_type=req.requirement_type,
                category=category,
                requirement_text=requirement_text,
                jd_evidence=req.raw_text,
                canonical_skill=canonical_skill,
                minimum_years=minimum_years,
                area=area,
                degree_level=degree_level,
                field_of_study=field_of_study,
                certification_name=certification_name,
                hard_requirement=req.hard_requirement,
                ambiguous=req.ambiguous,
                ambiguity_reason=req.ambiguity_reason,
            )
        )

    relationships = [
        RequirementRelationshipGroup(
            group_id=group.id,
            relationship=group.relationship,
            member_requirement_ids=list(group.member_ids),
            minimum_count=group.minimum_count,
            description=group.description,
        )
        for group in intelligence.relationships
    ]

    screening_constraints = [
        ScreeningConstraintInfo(
            constraint_id=constraint.id,
            constraint_type=constraint.constraint_type,
            status=constraint.status,
            statement=constraint.statement,
            raw_text=constraint.raw_text,
        )
        for constraint in intelligence.screening_constraints
    ]

    return items, relationships, screening_constraints


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
    or calls generate_job_intelligence/generate_requirement_intelligence.
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

    # Retained unchanged for lineage only - see the module docstring and
    # apps/api/models.py's `AtsAlignmentResult` docstring. Not read for
    # requirement content.
    job_intelligence_row = get_latest_job_intelligence(db, job_id=job_id)

    if job_intelligence_row is None:
        try:
            job_intelligence_row = generate_job_intelligence(db, job_id=job_id)
        except JobIntelligenceServiceError as exc:
            raise ATSAlignmentServiceError(
                "Unable to obtain Job Intelligence for this job.",
                status_code=exc.status_code,
            ) from exc

    # The actual requirement source (AJI-020C core integration rule). No
    # approved fallback exists if this is unavailable - see the module
    # docstring's "Fallback policy" note; a generation failure is
    # propagated exactly like the Job Intelligence failure above.
    requirement_intelligence_row = get_latest_requirement_intelligence(
        db, user_id=current_user.id, job_id=job_id
    )

    if requirement_intelligence_row is None:
        try:
            requirement_intelligence_row = generate_requirement_intelligence(
                db, user_id=current_user.id, job_id=job_id
            )
        except RequirementIntelligencePersistenceError as exc:
            raise ATSAlignmentServiceError(
                "Unable to obtain Requirement Intelligence for this job.",
                status_code=exc.status_code,
            ) from exc

    cached = (
        db.query(AtsAlignmentResult)
        .filter(
            AtsAlignmentResult.user_id == current_user.id,
            AtsAlignmentResult.job_id == job_id,
            AtsAlignmentResult.resume_version_id == resume_version.id,
            AtsAlignmentResult.job_intelligence_id == job_intelligence_row.id,
            AtsAlignmentResult.requirement_intelligence_id
            == requirement_intelligence_row.id,
            AtsAlignmentResult.engine_version == ENGINE_VERSION,
        )
        .order_by(AtsAlignmentResult.created_at.desc())
        .first()
    )

    if cached is not None:
        return cached

    intelligence = RequirementIntelligenceResult.model_validate(
        requirement_intelligence_row.structured_intelligence
    )
    job_requirements, relationships, screening_constraints = (
        _build_job_requirements_from_requirement_intelligence(intelligence)
    )

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

    result = evaluate_ats_alignment(
        job_requirements,
        resume_profile,
        relationships=relationships,
        screening_constraints=screening_constraints,
    )

    if result is None:
        raise ATSAlignmentServiceError(
            "Requirement Intelligence for this job contains no analyzable "
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
                "hard_requirement": item.hard_requirement,
                "ambiguous": item.ambiguous,
                "ambiguity_reason": item.ambiguity_reason,
            }
            for item in result.requirement_results
        ],
        "relationships": [
            {
                "group_id": group.group_id,
                "relationship": group.relationship,
                "member_requirement_ids": group.member_requirement_ids,
                "minimum_count": group.minimum_count,
                "description": group.description,
            }
            for group in result.relationships
        ],
        "screening_constraints": [
            {
                "constraint_id": constraint.constraint_id,
                "constraint_type": constraint.constraint_type,
                "status": constraint.status,
                "statement": constraint.statement,
                "raw_text": constraint.raw_text,
            }
            for constraint in result.screening_constraints
        ],
    }

    record = AtsAlignmentResult(
        user_id=current_user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        job_intelligence_id=job_intelligence_row.id,
        job_content_fingerprint=job_intelligence_row.content_fingerprint,
        requirement_intelligence_id=requirement_intelligence_row.id,
        requirement_intelligence_fingerprint=(
            requirement_intelligence_row.content_fingerprint
        ),
        engine_version=result.engine_version,
        overall_score=result.overall_score,
        confidence=result.confidence,
        result=result_data,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
