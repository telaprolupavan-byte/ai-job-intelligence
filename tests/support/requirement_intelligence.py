"""Builders for `RequirementIntelligence` rows (AJI-020A/B) shared by the
ATS Alignment, Gap Analysis and Resume Improvement tests.

These were previously copied into three test modules. This is the most
general of those copies: the parameters the other copies lacked are
optional and default to the values those copies hard-coded, so every
existing call behaves the same.
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
    `structured_intelligence`: the source ATS Alignment scores against
    since AJI-020C, and so also what Gap Analysis and Resume Improvement
    see through ATS Alignment. Validated through the real
    `RequirementIntelligenceResult` contract so a fixture can never drift
    from the actual AJI-020A schema. Controlled content (no incidental
    extraction noise from `job.description`/`job.requirements`) keeps
    assertions exact.
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
