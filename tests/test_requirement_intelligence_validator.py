import pytest

from apps.api.services.requirement_intelligence.deterministic import (
    DeterministicExtraction,
)
from apps.api.services.requirement_intelligence.validator import (
    RequirementIntelligenceValidationError,
    build_requirement_intelligence_result,
)


def _deterministic(**overrides) -> DeterministicExtraction:
    defaults = dict(
        seniority=None,
        requirements=[],
        relationships=[],
        screening_constraints=[],
        duplicate_groups=[],
        contradictions=[],
        ambiguous_requirement_ids=[],
        security_signals=[],
    )
    defaults.update(overrides)
    return DeterministicExtraction(**defaults)


RAW_TEXT = (
    "Senior AI Engineer. Python required. Machine learning is a great fit."
)


def _build(**overrides):
    defaults = dict(
        source_id="job-1",
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        model_provider="openai",
        model_name="test-model",
        extraction_status="complete",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(),
        ai_semantics=None,
    )
    defaults.update(overrides)
    return build_requirement_intelligence_result(**defaults)


def test_ai_field_accepted_with_matching_evidence():
    result = _build(
        ai_semantics={
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": "Senior AI Engineer",
            "normalized_title_confidence": "high",
        }
    )
    assert result.identity.normalized_title == "AI Engineer"
    assert result.identity.normalized_title_confidence == "high"
    assert result.identity.normalized_title_evidence == "Senior AI Engineer"


def test_ai_field_rejected_without_matching_evidence():
    """
    An AI-claimed field whose "evidence" does not actually appear in the
    raw JD text must be dropped rather than persisted/returned — the
    concrete anti-hallucination check (mirrors AJI-012).
    """
    result = _build(
        ai_semantics={
            "normalized_title": "Chief Executive Officer",
            "normalized_title_evidence": "text that is not in the JD",
            "normalized_title_confidence": "high",
        }
    )
    assert result.identity.normalized_title is None
    assert result.identity.normalized_title_confidence is None


def test_ai_field_rejected_without_any_evidence_quote():
    result = _build(
        ai_semantics={
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": None,
        }
    )
    assert result.identity.normalized_title is None


def test_deterministic_seniority_wins_over_ai():
    result = _build(
        deterministic=_deterministic(seniority="Senior"),
        ai_semantics={
            "seniority": "Staff",
            "seniority_evidence": "Senior AI Engineer",
            "seniority_confidence": "high",
        },
    )
    assert result.identity.seniority == "Senior"
    assert result.identity.seniority_confidence == "high"


def test_ai_seniority_fills_gap_when_deterministic_found_nothing():
    result = _build(
        deterministic=_deterministic(seniority=None),
        ai_semantics={
            "seniority": "Senior",
            "seniority_evidence": "Senior AI Engineer",
            "seniority_confidence": "high",
        },
    )
    assert result.identity.seniority == "Senior"


def test_domain_accepted_with_evidence():
    result = _build(
        ai_semantics={
            "domain": "Generative AI",
            "domain_evidence": "Machine learning is a great fit",
            "domain_confidence": "medium",
        }
    )
    assert result.domain.value == "Generative AI"


def test_domain_related_terms_filtered_to_terms_actually_in_text():
    result = _build(
        ai_semantics={
            "domain": "Generative AI",
            "domain_evidence": "Machine learning is a great fit",
            "domain_confidence": "medium",
            "domain_related_terms": ["Machine learning", "Fabricated Term XYZ"],
        }
    )
    assert result.domain.related_terms == ["Machine learning"]


def test_no_ai_semantics_produces_null_identity_and_domain_fields():
    result = _build(ai_semantics=None, extraction_status="partial")
    assert result.identity.normalized_title is None
    assert result.identity.role_family is None
    assert result.domain.value is None
    assert result.extraction_status == "partial"


def test_security_diagnostics_carried_through_from_deterministic():
    from apps.api.services.requirement_intelligence.contracts import (
        PromptInjectionSignal,
    )

    result = _build(
        deterministic=_deterministic(
            security_signals=[
                PromptInjectionSignal(
                    pattern_label="ignore_instructions",
                    evidence_text="ignore previous instructions",
                )
            ]
        )
    )
    assert result.security.prompt_injection_detected is True
    assert len(result.security.signals) == 1


def test_invalid_merge_raises_validation_error_not_silent_corruption():
    from apps.api.services.requirement_intelligence.contracts import (
        RequirementGroup,
    )

    with pytest.raises(RequirementIntelligenceValidationError):
        _build(
            deterministic=_deterministic(
                relationships=[
                    RequirementGroup(
                        id="grp-0001",
                        relationship="OR",
                        member_ids=["req-9999", "req-8888"],
                        description="either",
                        evidence_text="Python or Java",
                    )
                ]
            )
        )
