"""Requirement Intelligence orchestration (AJI-020A).

Unlike `apps.api.services.job_intelligence.service` (AJI-012, which owns
DB persistence/idempotency keyed off a `Job` row), this module is
deliberately DB-free: AJI-020A's scope is the requirement *model* and
its extraction pipeline, not a new persisted/queryable entity or API
surface — that wiring (if/when a consumer needs it) is left to AJI-020B,
per the ticket's own scope split. `build_requirement_intelligence()` is
the single, pure entry point a caller (a future service, a script, a
test) uses to go from raw JD text to a validated
`RequirementIntelligenceResult`; `analysis_version`/`analyzer_version`/
`prompt_version`/`model_provider`/`model_name` are still carried on every
result (see contracts.py), so a future persistence layer has everything
it needs to key/version snapshots exactly like `JobIntelligence` does.

Failure handling mirrors AJI-012: deterministic extraction failing is a
hard error (`RequirementIntelligenceServiceError`) — nothing is
returned. A failed *AI* call (provider error, timeout, invalid output)
degrades to an `extraction_status = "partial"` result containing only
the deterministic fields (identity.normalized_title/role_family/domain
stay unset) rather than discarding real, evidence-backed deterministic
data or raising.
"""

from __future__ import annotations

import logging

from apps.api.services.requirement_intelligence.deterministic import (
    RawRequirementSource,
    extract_deterministic,
)
from apps.api.services.requirement_intelligence.interpreter import (
    PROMPT_VERSION,
    RequirementIntelligenceInterpreter,
)
from apps.api.services.requirement_intelligence.providers import (
    create_requirement_intelligence_provider,
)
from apps.api.services.requirement_intelligence.providers.openai_provider import (
    RequirementIntelligenceProviderError,
)
from apps.api.services.requirement_intelligence.validator import (
    RequirementIntelligenceValidationError,
    build_requirement_intelligence_result,
)
from apps.api.services.requirement_intelligence.contracts import (
    RequirementIntelligenceResult,
)


ANALYSIS_VERSION = "1.0"
ANALYZER_VERSION = "1.0"

logger = logging.getLogger(__name__)


class RequirementIntelligenceServiceError(RuntimeError):
    """Application-level error for Requirement Intelligence orchestration
    failures."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def _raw_text(raw: RawRequirementSource) -> str:
    return "\n".join(
        part
        for part in [
            raw.title,
            raw.description,
            raw.requirements,
            raw.responsibilities,
        ]
        if part
    )


def build_requirement_intelligence(
    raw: RawRequirementSource, *, source_id: str
) -> RequirementIntelligenceResult:
    """Extract, semantically decode, validate, and assemble a
    `RequirementIntelligenceResult` for one JD snapshot.

    `source_id` is an opaque caller-supplied identifier (e.g. a job id or
    a content hash) — this module has no dependency on a `Job` ORM row
    or a database session.
    """
    try:
        deterministic = extract_deterministic(raw)
    except Exception as exc:
        logger.error(
            "Deterministic Requirement Intelligence extraction failed "
            "for source_id=%s: %s",
            source_id,
            exc,
        )
        raise RequirementIntelligenceServiceError(
            "Unable to extract Requirement Intelligence for this JD.",
            status_code=503,
        ) from exc

    raw_text = _raw_text(raw)

    ai_semantics: dict | None = None
    model_provider: str | None = None
    model_name: str | None = None

    try:
        provider = create_requirement_intelligence_provider()
        interpreter = RequirementIntelligenceInterpreter(provider)
        interpretation = interpreter.analyze(
            raw_jd_text=raw_text,
            deterministic_context={
                "seniority": deterministic.seniority,
                "required_skills": [
                    item.canonical_terms[0]
                    for item in deterministic.requirements
                    if item.requirement_type == "skill"
                    and item.importance == "required"
                    and item.canonical_terms
                ],
                "preferred_skills": [
                    item.canonical_terms[0]
                    for item in deterministic.requirements
                    if item.requirement_type == "skill"
                    and item.importance == "preferred"
                    and item.canonical_terms
                ],
            },
        )
        ai_semantics = interpretation.result
        model_provider = interpretation.provider
        model_name = interpretation.model
    except (RequirementIntelligenceProviderError, ValueError, RuntimeError) as exc:
        # A failed AI call never blocks or corrupts the deterministic
        # result: it degrades to a "partial" result instead.
        logger.error(
            "Requirement Intelligence AI semantics failed for "
            "source_id=%s: %s",
            source_id,
            exc,
        )
        ai_semantics = None

    try:
        return build_requirement_intelligence_result(
            source_id=source_id,
            analysis_version=ANALYSIS_VERSION,
            analyzer_version=ANALYZER_VERSION,
            prompt_version=PROMPT_VERSION,
            model_provider=model_provider,
            model_name=model_name,
            extraction_status="complete" if ai_semantics is not None else "partial",
            raw_title=raw.title,
            raw_text=raw_text,
            deterministic=deterministic,
            ai_semantics=ai_semantics,
        )
    except RequirementIntelligenceValidationError as exc:
        logger.error(
            "Requirement Intelligence validation failed for "
            "source_id=%s: %s",
            source_id,
            exc,
        )
        raise RequirementIntelligenceServiceError(
            "Unable to generate a valid Requirement Intelligence result.",
            status_code=503,
        ) from exc
