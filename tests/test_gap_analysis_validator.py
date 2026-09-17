"""Unit tests for the Gap Analysis (AJI-015) validator
(apps/api/services/gap_analysis/validator.py) — the concrete AI-safety /
evidence-grounding enforcement. No database, no real AI provider.
"""

from apps.api.services.gap_analysis.engine import GapCandidate
from apps.api.services.gap_analysis.validator import build_gap_analysis_result


def _missing_candidate(requirement_id="skill:rust") -> GapCandidate:
    return GapCandidate(
        requirement_id=requirement_id,
        requirement_type="skill",
        category="must_have",
        requirement_text="Rust",
        status="missing",
        jd_evidence="5+ years of Rust required.",
        resume_evidence=None,
    )


def _partial_candidate(requirement_id="skill:sql") -> GapCandidate:
    return GapCandidate(
        requirement_id=requirement_id,
        requirement_type="skill",
        category="preferred",
        requirement_text="SQL",
        status="partial",
        jd_evidence="SQL is a plus.",
        resume_evidence="Resume lists SQL in a skills section.",
    )


def _build(candidates, ai_semantics=None):
    return build_gap_analysis_result(
        analysis_version="1.0",
        job_id="job-1",
        resume_version_id="resume-version-1",
        ats_alignment_id="ats-1",
        candidates=candidates,
        ai_semantics=ai_semantics,
    )


# ---------------------------------------------------------------------------
# suggestion_type is never taken from the AI, regardless of what it says
# ---------------------------------------------------------------------------

def test_suggestion_type_for_missing_is_always_add_if_true_even_if_ai_disagrees():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:rust",
                "explanation": "The candidate clearly knows Rust already.",
                "explanation_evidence": "5+ years of Rust required.",
                "suggestion_text": "Rephrase your existing Rust experience.",
                "confidence": "high",
            }
        ]
    }

    result = _build([_missing_candidate()], ai_semantics)

    assert result.gaps[0].suggestion_type == "ADD_IF_TRUE"


def test_suggestion_type_for_partial_is_never_add_if_true():
    result = _build([_partial_candidate()], ai_semantics=None)

    assert result.gaps[0].suggestion_type == "REPHRASE_EXISTING"


# ---------------------------------------------------------------------------
# Evidence-substring grounding: unsupported AI evidence is rejected
# ---------------------------------------------------------------------------

def test_ai_explanation_rejected_when_evidence_not_verbatim_substring():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:rust",
                "explanation": "The JD strongly implies Rust experience.",
                "explanation_evidence": "This text does not appear anywhere.",
                "suggestion_text": "If you have Rust experience, add it.",
                "confidence": "high",
            }
        ]
    }

    result = _build([_missing_candidate()], ai_semantics)
    gap = result.gaps[0]

    assert gap.explanation_source == "deterministic"
    assert gap.suggestion_source == "deterministic"


def test_ai_explanation_accepted_when_evidence_is_verbatim_substring_of_jd_evidence():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:rust",
                "explanation": "Rust is a hard requirement with no resume match.",
                "explanation_evidence": "5+ years of Rust required.",
                "suggestion_text": "If you have Rust experience, consider adding it.",
                "confidence": "high",
            }
        ]
    }

    result = _build([_missing_candidate()], ai_semantics)
    gap = result.gaps[0]

    assert gap.explanation_source == "ai"
    assert gap.explanation == "Rust is a hard requirement with no resume match."


def test_ai_explanation_accepted_when_evidence_is_verbatim_substring_of_resume_evidence():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:sql",
                "explanation": "SQL is only listed, not demonstrated.",
                "explanation_evidence": "Resume lists SQL in a skills section.",
                "suggestion_text": (
                    "Consider expanding on Resume lists SQL in a skills "
                    "section to show real usage, if accurate."
                ),
                "confidence": "medium",
            }
        ]
    }

    result = _build([_partial_candidate()], ai_semantics)
    gap = result.gaps[0]

    assert gap.explanation_source == "ai"


def test_evidence_check_is_case_and_whitespace_insensitive():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:rust",
                "explanation": "Rust has no resume support.",
                "explanation_evidence": "5+   YEARS of rust required.",
                "suggestion_text": "If you have Rust experience, add it.",
                "confidence": "high",
            }
        ]
    }

    result = _build([_missing_candidate()], ai_semantics)

    assert result.gaps[0].explanation_source == "ai"


def test_missing_ai_entry_for_a_requirement_falls_back_to_deterministic():
    ai_semantics = {"gaps": []}

    result = _build([_missing_candidate()], ai_semantics)
    gap = result.gaps[0]

    assert gap.explanation_source == "deterministic"
    assert gap.suggestion_source == "deterministic"


# ---------------------------------------------------------------------------
# ADD_IF_TRUE suggestions must read as conditional, even with valid evidence
# ---------------------------------------------------------------------------

def test_add_if_true_suggestion_without_hedge_language_is_rejected():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:rust",
                "explanation": "Rust has no resume support.",
                "explanation_evidence": "5+ years of Rust required.",
                # No hedging language: reads as an assertion, not a
                # conditional prompt -- must be rejected even though the
                # evidence check passes.
                "suggestion_text": "Add your Rust experience to the resume.",
                "confidence": "high",
            }
        ]
    }

    result = _build([_missing_candidate()], ai_semantics)
    gap = result.gaps[0]

    assert gap.suggestion_source == "deterministic"
    assert "if you have" in gap.suggestion_text.lower()


def test_add_if_true_suggestion_with_hedge_language_is_accepted():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:rust",
                "explanation": "Rust has no resume support.",
                "explanation_evidence": "5+ years of Rust required.",
                "suggestion_text": (
                    "If you have production Rust experience, consider "
                    "adding it with specific project details."
                ),
                "confidence": "high",
            }
        ]
    }

    result = _build([_missing_candidate()], ai_semantics)
    gap = result.gaps[0]

    assert gap.suggestion_source == "ai"


def test_rephrase_suggestion_does_not_require_hedge_language():
    ai_semantics = {
        "gaps": [
            {
                "requirement_id": "skill:sql",
                "explanation": "SQL is only listed, not demonstrated.",
                "explanation_evidence": "Resume lists SQL in a skills section.",
                "suggestion_text": (
                    "Expand on Resume lists SQL in a skills section with "
                    "a concrete project example."
                ),
                "confidence": "medium",
            }
        ]
    }

    result = _build([_partial_candidate()], ai_semantics)
    gap = result.gaps[0]

    assert gap.suggestion_source == "ai"


# ---------------------------------------------------------------------------
# Never fabricates candidate experience: missing gaps never assert facts
# ---------------------------------------------------------------------------

def test_missing_gap_never_has_resume_evidence():
    result = _build([_missing_candidate()])

    assert result.gaps[0].resume_evidence is None


def test_ai_failure_still_produces_a_fully_safe_result():
    result = _build([_missing_candidate(), _partial_candidate()], ai_semantics=None)

    assert len(result.gaps) == 2
    assert all(gap.explanation_source == "deterministic" for gap in result.gaps)
    assert all(gap.suggestion_source == "deterministic" for gap in result.gaps)
    assert result.gaps[0].suggestion_type == "ADD_IF_TRUE"
    assert result.gaps[1].suggestion_type == "REPHRASE_EXISTING"


# ---------------------------------------------------------------------------
# Aggregate counts
# ---------------------------------------------------------------------------

def test_must_have_and_preferred_gap_counts():
    result = _build([_missing_candidate(), _partial_candidate()])

    assert result.must_have_gap_count == 1
    assert result.preferred_gap_count == 1


def test_empty_candidates_produce_empty_result():
    result = _build([])

    assert result.gaps == []
    assert result.must_have_gap_count == 0
    assert result.preferred_gap_count == 0
