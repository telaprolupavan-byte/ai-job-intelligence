"""Validation contract between deterministic extraction + AI semantic
decoding and the final persisted Job Intelligence result (AJI-012
section 20).

Deterministic fields (skills, experience, education, certifications,
responsibilities, authorization, compensation, location, employment) are
always trusted as-is: they were extracted from explicit patterns in the
JD text and never involve AI judgment.

AI-derived fields (identity.normalized_title, identity.role_family,
identity.seniority when not already deterministic, and domain) are only
ever accepted when the AI supplied an evidence quote that is actually
present (case/whitespace-insensitive substring match) in the raw JD
text. This is the concrete anti-hallucination check: an AI-invented
value with no matching evidence is dropped rather than persisted.
"""

from __future__ import annotations

import re
from typing import Any

from apps.api.services.job_intelligence.contracts import (
    DomainInfo,
    JobIdentity,
    JobIntelligenceResult,
)
from apps.api.services.job_intelligence.deterministic import (
    DeterministicExtraction,
)


class JobIntelligenceValidationError(RuntimeError):
    """Raised when a Job Intelligence result fails validation and must
    not be persisted."""


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
) -> JobIdentity:
    identity = JobIdentity(
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
        identity.normalized_title_confidence = (
            ai_semantics.get("normalized_title_confidence") or "medium"
        )

    role_family = ai_semantics.get("role_family")
    if role_family and _evidence_supported(
        ai_semantics.get("role_family_evidence"), raw_text
    ):
        identity.role_family = role_family
        identity.role_family_confidence = (
            ai_semantics.get("role_family_confidence") or "medium"
        )

    # Deterministic title-keyword seniority always wins; the AI only
    # fills the gap when deterministic extraction found nothing.
    if identity.seniority is None:
        seniority = ai_semantics.get("seniority")
        if seniority and _evidence_supported(
            ai_semantics.get("seniority_evidence"), raw_text
        ):
            identity.seniority = seniority
            identity.seniority_confidence = (
                ai_semantics.get("seniority_confidence") or "medium"
            )

    return identity


def _build_domain(
    *,
    raw_text: str,
    ai_semantics: dict[str, Any] | None,
) -> DomainInfo:
    if not ai_semantics:
        return DomainInfo()

    value = ai_semantics.get("domain")
    evidence = ai_semantics.get("domain_evidence")

    if value and _evidence_supported(evidence, raw_text):
        return DomainInfo(
            value=value,
            confidence=ai_semantics.get("domain_confidence") or "medium",
            evidence_text=evidence,
        )

    return DomainInfo()


def _validate_no_duplicate_or_overlapping_skills(
    result: JobIntelligenceResult,
) -> None:
    seen_required: set[str] = set()

    for item in result.required_skills:
        if item.canonical_skill in seen_required:
            raise JobIntelligenceValidationError(
                f"Duplicate required skill: {item.canonical_skill}"
            )
        seen_required.add(item.canonical_skill)

    seen_preferred: set[str] = set()

    for item in result.preferred_skills:
        if item.canonical_skill in seen_preferred:
            raise JobIntelligenceValidationError(
                f"Duplicate preferred skill: {item.canonical_skill}"
            )
        seen_preferred.add(item.canonical_skill)

    overlap = seen_required & seen_preferred
    if overlap:
        raise JobIntelligenceValidationError(
            f"Skill(s) present in both required and preferred: {overlap}"
        )


def build_job_intelligence_result(
    *,
    job_id: str,
    analysis_version: str,
    raw_title: str,
    raw_text: str,
    deterministic: DeterministicExtraction,
    ai_semantics: dict[str, Any] | None,
) -> JobIntelligenceResult:
    """
    Merge deterministic extraction with (optional) validated AI
    semantics into the final Job Intelligence contract, raising
    `JobIntelligenceValidationError` rather than returning a malformed
    result if validation fails.
    """
    result = JobIntelligenceResult(
        analysis_version=analysis_version,
        job_id=job_id,
        identity=_build_identity(
            raw_title=raw_title,
            deterministic=deterministic,
            raw_text=raw_text,
            ai_semantics=ai_semantics,
        ),
        employment=deterministic.employment,
        location=deterministic.location,
        required_skills=deterministic.required_skills,
        preferred_skills=deterministic.preferred_skills,
        required_experience=deterministic.required_experience,
        preferred_experience=deterministic.preferred_experience,
        education=deterministic.education,
        certifications=deterministic.certifications,
        responsibilities=deterministic.responsibilities,
        authorization=deterministic.authorization,
        compensation=deterministic.compensation,
        domain=_build_domain(raw_text=raw_text, ai_semantics=ai_semantics),
    )

    _validate_no_duplicate_or_overlapping_skills(result)

    return result
