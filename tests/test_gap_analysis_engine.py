"""Unit tests for the Gap Analysis (AJI-015) pure, DB-free engine
(apps/api/services/gap_analysis/engine.py). No database, no AI.
"""

from apps.api.services.gap_analysis.engine import (
    GapCandidate,
    default_suggestion_type,
    deterministic_explanation,
    deterministic_suggestion_text,
    select_gap_candidates,
)


def _requirement_result(
    *,
    requirement_id="skill:python",
    requirement_type="skill",
    category="must_have",
    requirement_text="Python",
    status="missing",
    jd_evidence="Python required.",
    resume_evidence=None,
):
    return {
        "requirement_id": requirement_id,
        "requirement_type": requirement_type,
        "category": category,
        "requirement_text": requirement_text,
        "status": status,
        "jd_evidence": jd_evidence,
        "resume_evidence": resume_evidence,
        "explanation": "ATS explanation (never reused by Gap Analysis).",
        "confidence": "high",
    }


# ---------------------------------------------------------------------------
# select_gap_candidates: only non-matched requirements, never re-scored
# ---------------------------------------------------------------------------

def test_matched_requirement_is_never_a_gap():
    results = [_requirement_result(status="matched")]

    assert select_gap_candidates(results) == []


def test_missing_and_partial_requirements_are_selected():
    results = [
        _requirement_result(requirement_id="skill:python", status="missing"),
        _requirement_result(
            requirement_id="skill:sql",
            status="partial",
            resume_evidence="Resume lists SQL in a skills section.",
        ),
        _requirement_result(requirement_id="skill:go", status="matched"),
    ]

    candidates = select_gap_candidates(results)

    assert {c.requirement_id for c in candidates} == {"skill:python", "skill:sql"}


def test_gap_candidate_fields_are_copied_verbatim_not_recomputed():
    results = [
        _requirement_result(
            requirement_id="skill:kubernetes",
            requirement_type="skill",
            category="preferred",
            requirement_text="Kubernetes",
            status="partial",
            jd_evidence="Kubernetes is a plus.",
            resume_evidence="Resume lists Kubernetes in a skills section.",
        )
    ]

    [candidate] = select_gap_candidates(results)

    assert candidate == GapCandidate(
        requirement_id="skill:kubernetes",
        requirement_type="skill",
        category="preferred",
        requirement_text="Kubernetes",
        status="partial",
        jd_evidence="Kubernetes is a plus.",
        resume_evidence="Resume lists Kubernetes in a skills section.",
    )


def test_no_gaps_when_all_requirements_matched():
    results = [
        _requirement_result(requirement_id="skill:python", status="matched"),
        _requirement_result(requirement_id="skill:sql", status="matched"),
    ]

    assert select_gap_candidates(results) == []


def test_empty_requirement_results_produce_no_gaps():
    assert select_gap_candidates([]) == []


# ---------------------------------------------------------------------------
# default_suggestion_type: the evidence-safety-critical mapping
# ---------------------------------------------------------------------------

def test_missing_status_always_maps_to_add_if_true():
    assert default_suggestion_type("missing") == "ADD_IF_TRUE"


def test_partial_status_always_maps_to_rephrase_existing():
    assert default_suggestion_type("partial") == "REPHRASE_EXISTING"


# ---------------------------------------------------------------------------
# Deterministic templates never fabricate anything beyond given evidence
# ---------------------------------------------------------------------------

def test_deterministic_explanation_for_missing_never_claims_evidence():
    candidate = GapCandidate(
        requirement_id="skill:rust",
        requirement_type="skill",
        category="must_have",
        requirement_text="Rust",
        status="missing",
        jd_evidence="Rust required.",
        resume_evidence=None,
    )

    explanation = deterministic_explanation(candidate)

    assert "Rust" in explanation
    assert "no matching evidence" in explanation.lower()


def test_deterministic_explanation_for_partial_references_resume_evidence():
    candidate = GapCandidate(
        requirement_id="skill:sql",
        requirement_type="skill",
        category="preferred",
        requirement_text="SQL",
        status="partial",
        jd_evidence="SQL is a plus.",
        resume_evidence="Resume lists SQL in a skills section.",
    )

    explanation = deterministic_explanation(candidate)

    assert "Resume lists SQL in a skills section." in explanation


def test_deterministic_suggestion_text_for_add_if_true_is_conditional():
    candidate = GapCandidate(
        requirement_id="skill:rust",
        requirement_type="skill",
        category="must_have",
        requirement_text="Rust",
        status="missing",
        jd_evidence="Rust required.",
        resume_evidence=None,
    )

    suggestion = deterministic_suggestion_text(candidate, "ADD_IF_TRUE")

    assert "if you have" in suggestion.lower()
    assert "truthful" in suggestion.lower()


def test_deterministic_suggestion_text_for_rephrase_references_resume_evidence():
    candidate = GapCandidate(
        requirement_id="skill:sql",
        requirement_type="skill",
        category="preferred",
        requirement_text="SQL",
        status="partial",
        jd_evidence="SQL is a plus.",
        resume_evidence="Resume lists SQL in a skills section.",
    )

    suggestion = deterministic_suggestion_text(candidate, "REPHRASE_EXISTING")

    assert "Resume lists SQL in a skills section." in suggestion
