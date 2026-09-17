"""Pydantic contract validation tests for Gap Analysis (AJI-015)
(apps/api/services/gap_analysis/contracts.py). No database, no AI.
"""

import pytest
from pydantic import ValidationError

from apps.api.services.gap_analysis.contracts import (
    GapAnalysisResult,
    GapSuggestion,
)


def _gap_suggestion(**overrides) -> dict:
    base = {
        "requirement_id": "skill:python",
        "requirement_type": "skill",
        "category": "must_have",
        "requirement_text": "Python",
        "status": "missing",
        "jd_evidence": "Python required.",
        "resume_evidence": None,
        "suggestion_type": "ADD_IF_TRUE",
        "explanation": "No Python evidence found.",
        "explanation_source": "deterministic",
        "suggestion_text": "If you have Python experience, consider adding it.",
        "suggestion_source": "deterministic",
        "confidence": "medium",
    }
    base.update(overrides)
    return base


def test_valid_gap_suggestion_round_trips():
    suggestion = GapSuggestion(**_gap_suggestion())

    assert suggestion.status == "missing"
    assert suggestion.suggestion_type == "ADD_IF_TRUE"


def test_gap_suggestion_rejects_invalid_status():
    with pytest.raises(ValidationError):
        GapSuggestion(**_gap_suggestion(status="matched"))


def test_gap_suggestion_rejects_invalid_suggestion_type():
    with pytest.raises(ValidationError):
        GapSuggestion(**_gap_suggestion(suggestion_type="INVENT_EXPERIENCE"))


def test_gap_suggestion_rejects_empty_requirement_text():
    with pytest.raises(ValidationError):
        GapSuggestion(**_gap_suggestion(requirement_text=""))


def test_gap_suggestion_rejects_empty_jd_evidence():
    with pytest.raises(ValidationError):
        GapSuggestion(**_gap_suggestion(jd_evidence=""))


def test_gap_analysis_result_with_no_gaps_is_valid():
    result = GapAnalysisResult(
        analysis_version="1.0",
        job_id="job-1",
        resume_version_id="resume-1",
        ats_alignment_id="ats-1",
    )

    assert result.gaps == []
    assert result.must_have_gap_count == 0
    assert result.preferred_gap_count == 0


def test_gap_analysis_result_with_gaps():
    result = GapAnalysisResult(
        analysis_version="1.0",
        job_id="job-1",
        resume_version_id="resume-1",
        ats_alignment_id="ats-1",
        must_have_gap_count=1,
        gaps=[GapSuggestion(**_gap_suggestion())],
    )

    assert len(result.gaps) == 1
