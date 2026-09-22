"""Validation contract between deterministic extraction + AI semantic
decoding and the final persisted Requirement Intelligence result
(AJI-020A).

Deterministic fields (requirements, relationships, screening
constraints, duplicate/contradiction diagnostics, and seniority when the
title supports it) are always trusted as-is: they were extracted from
explicit patterns in the JD text and never involve AI judgment.

AI-derived fields (identity.normalized_title, identity.role_family,
identity.seniority when not already deterministic, domain, and
domain.related_terms) are only ever accepted when the AI supplied an
evidence quote that is actually present (case/whitespace-insensitive
substring match) in the raw JD text. This is the concrete
anti-hallucination check, mirroring `job_intelligence.validator`: an
AI-invented value with no matching evidence is dropped rather than
persisted, regardless of what an embedded prompt-injection attempt in
the JD asked the model to output (see prompts.py and
contracts.SecurityDiagnostics for the rest of the JD prompt-injection
defense).
"""

from __future__ import annotations

import re
from typing import Any

from apps.api.services.requirement_intelligence.contracts import (
    DomainTerminology,
    QualityDiagnostics,
    RequirementIntelligenceResult,
    SecurityDiagnostics,
    TitleSeniorityInfo,
)
from apps.api.services.requirement_intelligence.deterministic import (
    DeterministicExtraction,
)


class RequirementIntelligenceValidationError(RuntimeError):
    """Raised when a Requirement Intelligence result fails validation and
    must not be persisted/returned."""


# The only values the contract's `Confidence` literal accepts - see
# apps/api/services/job_intelligence/validator.py, which screens the same
# four AI confidence fields for the same two reasons: a confidence set by
# *assignment* onto an already-built `TitleSeniorityInfo` is not
# re-validated by Pydantic (an out-of-contract value would be persisted
# and served as if valid), and one passed to the `DomainTerminology`
# *constructor* raises, discarding an otherwise-valid snapshot over a
# single unrepresentable field. Case is normalized rather than rejected.
_ALLOWED_CONFIDENCE = ("high", "medium", "low")
_DEFAULT_CONFIDENCE = "medium"


def _validated_confidence(value: Any) -> str:
    if not isinstance(value, str):
        return _DEFAULT_CONFIDENCE

    normalized = value.strip().lower()

    if normalized in _ALLOWED_CONFIDENCE:
        return normalized

    return _DEFAULT_CONFIDENCE


def _normalize_for_comparison(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _evidence_supported(evidence: str | None, raw_text: str) -> bool:
    if not evidence:
        return False

    normalized_evidence = _normalize_for_comparison(evidence)

    if not normalized_evidence:
        return False

    return normalized_evidence in _normalize_for_comparison(raw_text)


def _build_identity(
    *,
    raw_title: str,
    deterministic: DeterministicExtraction,
    raw_text: str,
    ai_semantics: dict[str, Any] | None,
) -> TitleSeniorityInfo:
    identity = TitleSeniorityInfo(
        original_title=raw_title,
        seniority=deterministic.seniority,
        seniority_confidence="high" if deterministic.seniority else None,
    )

    if not ai_semantics:
        return identity

    normalized_title = ai_semantics.get("normalized_title")
    if normalized_title and _evidence_supported(
        ai_semantics.get("normalized_title_evidence"), raw_text
    ):
        identity.normalized_title = normalized_title
        identity.normalized_title_evidence = ai_semantics.get(
            "normalized_title_evidence"
        )
        identity.normalized_title_confidence = (
            _validated_confidence(ai_semantics.get("normalized_title_confidence"))
        )

    role_family = ai_semantics.get("role_family")
    if role_family and _evidence_supported(
        ai_semantics.get("role_family_evidence"), raw_text
    ):
        identity.role_family = role_family
        identity.role_family_evidence = ai_semantics.get("role_family_evidence")
        identity.role_family_confidence = (
            _validated_confidence(ai_semantics.get("role_family_confidence"))
        )

    # Deterministic title-keyword seniority always wins; the AI only
    # fills the gap when deterministic extraction found nothing.
    if identity.seniority is None:
        seniority = ai_semantics.get("seniority")
        if seniority and _evidence_supported(
            ai_semantics.get("seniority_evidence"), raw_text
        ):
            identity.seniority = seniority
            identity.seniority_evidence = ai_semantics.get("seniority_evidence")
            identity.seniority_confidence = (
                _validated_confidence(ai_semantics.get("seniority_confidence"))
            )

    return identity


def _build_domain(
    *,
    raw_text: str,
    ai_semantics: dict[str, Any] | None,
) -> DomainTerminology:
    if not ai_semantics:
        return DomainTerminology()

    value = ai_semantics.get("domain")
    evidence = ai_semantics.get("domain_evidence")

    related_terms = [
        term
        for term in ai_semantics.get("domain_related_terms") or []
        if isinstance(term, str)
        and term.strip()
        and _normalize_for_comparison(term) in _normalize_for_comparison(raw_text)
    ]

    if value and _evidence_supported(evidence, raw_text):
        return DomainTerminology(
            value=value,
            confidence=_validated_confidence(ai_semantics.get("domain_confidence")),
            evidence_text=evidence,
            related_terms=related_terms,
        )

    return DomainTerminology(related_terms=related_terms)


def build_requirement_intelligence_result(
    *,
    source_id: str,
    analysis_version: str,
    analyzer_version: str,
    prompt_version: str,
    model_provider: str | None,
    model_name: str | None,
    extraction_status: str,
    raw_title: str,
    raw_text: str,
    deterministic: DeterministicExtraction,
    ai_semantics: dict[str, Any] | None,
) -> RequirementIntelligenceResult:
    """
    Merge deterministic extraction with (optional) validated AI
    semantics into the final Requirement Intelligence contract, raising
    `RequirementIntelligenceValidationError` rather than returning a
    malformed result if validation fails.
    """
    try:
        result = RequirementIntelligenceResult(
            analysis_version=analysis_version,
            analyzer_version=analyzer_version,
            prompt_version=prompt_version,
            model_provider=model_provider,
            model_name=model_name,
            extraction_status=extraction_status,
            source_id=source_id,
            identity=_build_identity(
                raw_title=raw_title,
                deterministic=deterministic,
                raw_text=raw_text,
                ai_semantics=ai_semantics,
            ),
            domain=_build_domain(raw_text=raw_text, ai_semantics=ai_semantics),
            requirements=deterministic.requirements,
            relationships=deterministic.relationships,
            screening_constraints=deterministic.screening_constraints,
            quality=QualityDiagnostics(
                duplicate_groups=deterministic.duplicate_groups,
                contradictions=deterministic.contradictions,
                ambiguous_requirement_ids=deterministic.ambiguous_requirement_ids,
            ),
            security=SecurityDiagnostics(
                prompt_injection_detected=bool(deterministic.security_signals),
                signals=deterministic.security_signals,
            ),
        )
    except ValueError as exc:
        raise RequirementIntelligenceValidationError(str(exc)) from exc

    return result
