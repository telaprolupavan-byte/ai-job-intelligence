"""Builders for persisted AJI-020A/B `RequirementIntelligence` rows and
their requirement items, shared by the ATS Alignment, Gap Analysis and
Resume Improvement tests.

`make_requirement_intelligence` validates its payload through the real
`RequirementIntelligenceResult` contract so a fixture can never drift
from the actual AJI-020A schema.
"""

from uuid import uuid4

from apps.api.models import Job, RequirementIntelligence, User
from apps.api.services.requirement_intelligence.contracts import (
    RequirementIntelligenceResult,
)


def ri_skill_item(
    canonical_skill: str, *, importance: str = "required", item_id: str | None = None
) -> dict:
    return {
        "id": item_id or f"req-skill-{canonical_skill}",
        "requirement_type": "skill",
        "importance": importance,
        "statement": f"{canonical_skill} ({importance})",
        "canonical_terms": [canonical_skill],
        "raw_text": f"{canonical_skill} {importance}.",
        "confidence": "high",
    }


def ri_experience_item(
    minimum_years: float,
    *,
    area: str | None = None,
    importance: str = "required",
    item_id: str | None = None,
) -> dict:
    return {
        "id": item_id or f"req-experience-{area or 'general'}",
        "requirement_type": "experience",
        "importance": importance,
        "statement": f"{minimum_years}+ years" + (f" of {area}" if area else ""),
        "canonical_terms": [area] if area else [],
        "raw_text": f"{minimum_years}+ years of experience required.",
        "confidence": "high",
        "experience": {
            "operator": "at_least",
            "minimum_years": minimum_years,
            "area": area,
        },
    }


def make_requirement_intelligence(
    db,
    *,
    job: Job,
    user: User,
    requirements: list[dict] | None = None,
    relationships: list[dict] | None = None,
    screening_constraints: list[dict] | None = None,
    content_fingerprint: str | None = None,
) -> RequirementIntelligence:
    """
    Directly persists a `RequirementIntelligence` row with hand-crafted
    `structured_intelligence`, mirroring `make_job_intelligence`'s role
    for the old JobIntelligence-based tests. Validated through the real
    `RequirementIntelligenceResult` contract so a fixture can never drift
    from the actual AJI-020A schema.
    """
    payload = {
        "analysis_version": "1.0",
        "analyzer_version": "1.0",
        "prompt_version": "1.0",
        "model_provider": None,
        "model_name": None,
        "extraction_status": "complete",
        "source_id": str(job.id),
        "identity": {"original_title": job.title},
        "domain": {},
        "requirements": requirements or [],
        "relationships": relationships or [],
        "screening_constraints": screening_constraints or [],
        "quality": {},
        "security": {},
    }
    validated = RequirementIntelligenceResult.model_validate(payload)

    record = RequirementIntelligence(
        id=uuid4(),
        user_id=user.id,
        job_id=job.id,
        content_fingerprint=content_fingerprint or f"fingerprint-{uuid4()}",
        raw_jd_snapshot={"title": job.title},
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        extraction_status="complete",
        structured_intelligence=validated.model_dump(mode="json"),
    )
    db.add(record)
    db.flush()

    return record
