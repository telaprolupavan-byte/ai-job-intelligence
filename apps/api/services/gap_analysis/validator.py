"""Validation contract between deterministic gap candidates + AI semantic
enrichment and the final persisted Gap Analysis result (AJI-015).

Every gap's requirement_id/requirement_type/category/requirement_text/
status/jd_evidence/resume_evidence is always trusted as-is — it is
copied verbatim from an existing AJI-013 `AtsAlignmentResult` and never
re-decided here (Gap Analysis does not reimplement ATS scoring).

`suggestion_type` is always deterministic
(`engine.default_suggestion_type`) and is NEVER taken from the AI,
regardless of what it returns — this is the concrete mechanical
guarantee behind "missing candidate evidence must produce an
ADD_IF_TRUE-style recommendation rather than fabricated resume content".

`explanation` / `suggestion_text` MAY come from the AI, but only when:

- the AI returned a value for that exact `requirement_id`, and
- its `explanation_evidence` is a verbatim (case/whitespace-insensitive)
  substring of that gap's own `jd_evidence` + `resume_evidence` — never
  the full raw JD/resume text — which keeps the AI's grounding scoped to
  the one requirement it was asked about, mirroring
  `apps.api.services.job_intelligence.validator`'s evidence-substring
  anti-hallucination check, and
- for an `ADD_IF_TRUE` gap specifically, its `suggestion_text` contains
  an explicit conditional/hedging phrase (see `_HEDGE_PHRASES`) — a
  sentence that asserts the candidate has the skill without hedging is
  rejected even if the evidence check passed, since an `ADD_IF_TRUE` gap
  has zero resume evidence to ground any factual claim in.

Any AI output failing these checks for a given field on a given gap
silently falls back to the deterministic template for that one field —
one bad AI field never discards the rest of an otherwise-valid, safe
result (the same silent-and-safe pattern Job Intelligence's
`_evidence_supported()` established).
"""

from __future__ import annotations

import re
from typing import Any

from apps.api.services.gap_analysis.contracts import (
    GapAnalysisResult,
    GapSuggestion,
)
from apps.api.services.gap_analysis.engine import (
    GapCandidate,
    default_suggestion_type,
    deterministic_explanation,
    deterministic_suggestion_text,
)


class GapAnalysisValidationError(RuntimeError):
    """Raised when a Gap Analysis result fails validation and must not be
    persisted."""


# A non-exhaustive but deliberately explicit set of conditional/hedging
# phrases. `ADD_IF_TRUE` suggestion text must contain at least one of
# these — an AI suggestion phrased as a flat assertion ("Add your
# Kubernetes experience...") is rejected regardless of evidence, since an
# ADD_IF_TRUE gap by definition has no resume evidence to assert from.
_HEDGE_PHRASES = (
    "if you have",
    "if you've",
    "if you actually",
    "if you do",
    "if this is true",
    "if this is accurate",
    "if accurate",
    "if true",
    "if applicable",
    "if so",
    "consider adding if",
    "only if",
)


def _normalize_for_comparison(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _evidence_supported(evidence: str | None, grounding_text: str) -> bool:
    if not evidence:
        return False

    normalized_evidence = _normalize_for_comparison(evidence)

    if not normalized_evidence:
        return False

    return normalized_evidence in _normalize_for_comparison(grounding_text)


# The only confidence values `GapSuggestion.confidence` accepts. An AI
# that answers "High", "very high" or `0.9` is returning a value this
# contract has no representation for; it is treated like any other
# rejected AI field (fall back to the deterministic default) rather than
# being handed to Pydantic, which would raise and discard the whole
# analysis. Case is normalized rather than rejected - "High" means the
# same thing as "high" and carries real signal.
_ALLOWED_CONFIDENCE = ("high", "medium", "low")
_DEFAULT_CONFIDENCE = "medium"


def _validated_confidence(value: Any) -> str:
    if not isinstance(value, str):
        return _DEFAULT_CONFIDENCE

    normalized = value.strip().lower()

    if normalized in _ALLOWED_CONFIDENCE:
        return normalized

    return _DEFAULT_CONFIDENCE


def _has_hedge_language(text: str) -> bool:
    normalized = _normalize_for_comparison(text)
    return any(phrase in normalized for phrase in _HEDGE_PHRASES)


def _build_gap_suggestion(
    candidate: GapCandidate,
    ai_item: dict[str, Any] | None,
) -> GapSuggestion:
    suggestion_type = default_suggestion_type(candidate.status)

    grounding_text = f"{candidate.jd_evidence} {candidate.resume_evidence or ''}"

    explanation = deterministic_explanation(candidate)
    explanation_source = "deterministic"
    suggestion_text = deterministic_suggestion_text(candidate, suggestion_type)
    suggestion_source = "deterministic"
    confidence = "medium"

    if ai_item:
        ai_explanation = ai_item.get("explanation")
        ai_evidence = ai_item.get("explanation_evidence")
        ai_suggestion_text = ai_item.get("suggestion_text")
        ai_confidence = _validated_confidence(ai_item.get("confidence"))

        evidence_ok = _evidence_supported(ai_evidence, grounding_text)

        if ai_explanation and evidence_ok:
            explanation = ai_explanation
            explanation_source = "ai"
            confidence = ai_confidence

        if ai_suggestion_text and evidence_ok:
            if suggestion_type == "ADD_IF_TRUE":
                # Extra safety net on top of the evidence check: an
                # ADD_IF_TRUE suggestion must read as conditional, never
                # as an assertion the candidate already has the skill.
                if _has_hedge_language(ai_suggestion_text):
                    suggestion_text = ai_suggestion_text
                    suggestion_source = "ai"
            else:
                suggestion_text = ai_suggestion_text
                suggestion_source = "ai"

    return GapSuggestion(
        requirement_id=candidate.requirement_id,
        requirement_type=candidate.requirement_type,
        category=candidate.category,
        requirement_text=candidate.requirement_text,
        status=candidate.status,
        jd_evidence=candidate.jd_evidence,
        resume_evidence=candidate.resume_evidence,
        suggestion_type=suggestion_type,
        explanation=explanation,
        explanation_source=explanation_source,
        suggestion_text=suggestion_text,
        suggestion_source=suggestion_source,
        confidence=confidence,
    )


def build_gap_analysis_result(
    *,
    analysis_version: str,
    job_id: str,
    resume_version_id: str,
    ats_alignment_id: str,
    candidates: list[GapCandidate],
    ai_semantics: dict[str, Any] | None,
) -> GapAnalysisResult:
    """
    Merge deterministic gap candidates with (optional) validated AI
    enrichment into the final Gap Analysis contract. Never raises for a
    rejected individual AI field (those silently fall back to the
    deterministic template) — only a structurally invalid result
    (caught by `GapSuggestion`'s/`GapAnalysisResult`'s own Pydantic
    validation) would ever surface as `GapAnalysisValidationError` to
    the caller, never as a raw Pydantic error.
    """
    ai_gaps_by_requirement_id: dict[str, dict[str, Any]] = {}

    if ai_semantics:
        for item in ai_semantics.get("gaps", []) or []:
            requirement_id = item.get("requirement_id")
            if requirement_id:
                ai_gaps_by_requirement_id[requirement_id] = item

    # Building the individual gaps is inside the same guard as the final
    # result: `GapSuggestion` is itself a validated model, so an AI value
    # this module has not explicitly screened must still surface as
    # `GapAnalysisValidationError` (which the service turns into a
    # controlled 503) rather than escaping as a raw Pydantic
    # `ValidationError` and becoming an unhandled 500.
    try:
        gaps = [
            _build_gap_suggestion(
                candidate,
                ai_gaps_by_requirement_id.get(candidate.requirement_id),
            )
            for candidate in candidates
        ]

        must_have_gap_count = sum(
            1 for gap in gaps if gap.category == "must_have"
        )
        preferred_gap_count = sum(
            1 for gap in gaps if gap.category == "preferred"
        )

        return GapAnalysisResult(
            analysis_version=analysis_version,
            job_id=job_id,
            resume_version_id=resume_version_id,
            ats_alignment_id=ats_alignment_id,
            must_have_gap_count=must_have_gap_count,
            preferred_gap_count=preferred_gap_count,
            gaps=gaps,
        )
    except Exception as exc:
        raise GapAnalysisValidationError(str(exc)) from exc
