import pytest

from apps.api.services.job_intelligence.contracts import (
    EmploymentInfo,
    LocationInfo,
    SkillRequirement,
)
from apps.api.services.job_intelligence.deterministic import (
    DeterministicExtraction,
)
from apps.api.services.job_intelligence.validator import (
    JobIntelligenceValidationError,
    build_job_intelligence_result,
)


def _deterministic(**overrides) -> DeterministicExtraction:
    defaults = dict(
        seniority=None,
        employment=EmploymentInfo(),
        location=LocationInfo(),
    )
    defaults.update(overrides)
    return DeterministicExtraction(**defaults)


RAW_TEXT = "Senior AI Engineer. Python required. Machine learning is a great fit."


def test_ai_field_accepted_with_matching_evidence():
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(),
        ai_semantics={
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": "Senior AI Engineer",
            "normalized_title_confidence": "high",
        },
    )

    assert result.identity.normalized_title == "AI Engineer"
    assert result.identity.normalized_title_confidence == "high"


def test_ai_field_rejected_without_matching_evidence():
    """
    An AI-claimed field whose "evidence" does not actually appear in the
    raw JD text must be dropped rather than persisted — the concrete
    anti-hallucination check (AJI-012 section 19/20).
    """
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(),
        ai_semantics={
            "normalized_title": "Chief Executive Officer",
            "normalized_title_evidence": "This text does not appear anywhere.",
        },
    )

    assert result.identity.normalized_title is None
    assert result.identity.normalized_title_confidence is None


def test_ai_field_rejected_without_any_evidence_text():
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(),
        ai_semantics={"domain": "FinTech", "domain_evidence": None},
    )

    assert result.domain.value is None


def test_deterministic_seniority_wins_over_ai():
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(seniority="Senior"),
        ai_semantics={
            "seniority": "Staff",
            "seniority_evidence": "Senior AI Engineer",
        },
    )

    assert result.identity.seniority == "Senior"
    assert result.identity.seniority_confidence == "high"


def test_ai_fills_seniority_gap_when_deterministic_found_nothing():
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="AI Engineer",
        raw_text="AI Engineer. Machine learning is a great fit.",
        deterministic=_deterministic(seniority=None),
        ai_semantics={
            "seniority": "Mid",
            "seniority_evidence": "Machine learning is a great fit",
        },
    )

    assert result.identity.seniority == "Mid"
    assert result.identity.seniority_confidence == "medium"


def test_no_ai_semantics_still_produces_valid_result():
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(),
        ai_semantics=None,
    )

    assert result.identity.normalized_title is None
    assert result.domain.value is None


def test_duplicate_required_skill_rejected():
    deterministic = _deterministic(
        required_skills=[
            SkillRequirement(
                canonical_skill="python",
                level="required",
                evidence_text="Python required",
            ),
            SkillRequirement(
                canonical_skill="python",
                level="required",
                evidence_text="Python is required",
            ),
        ]
    )

    with pytest.raises(JobIntelligenceValidationError):
        build_job_intelligence_result(
            job_id="job-1",
            analysis_version="1.0",
            raw_title="AI Engineer",
            raw_text=RAW_TEXT,
            deterministic=deterministic,
            ai_semantics=None,
        )


def test_skill_in_both_required_and_preferred_rejected():
    deterministic = _deterministic(
        required_skills=[
            SkillRequirement(
                canonical_skill="python",
                level="required",
                evidence_text="Python required",
            ),
        ],
        preferred_skills=[
            SkillRequirement(
                canonical_skill="python",
                level="preferred",
                evidence_text="Python preferred",
            ),
        ],
    )

    with pytest.raises(JobIntelligenceValidationError):
        build_job_intelligence_result(
            job_id="job-1",
            analysis_version="1.0",
            raw_title="AI Engineer",
            raw_text=RAW_TEXT,
            deterministic=deterministic,
            ai_semantics=None,
        )


# ---------------------------------------------------------------------------
# An out-of-contract `*_confidence` from the AI is a rejected field, not
# a silently-persisted value and not a crash.
#
# The contract's Confidence is Literal["high","medium","low"]. Before
# these were screened, the two AI confidence paths failed in two
# different ways:
#
#   - identity.*_confidence is set by *assignment* onto an already-built
#     JobIdentity, which Pydantic does not re-validate - so "super-high"
#     was persisted into structured_intelligence and served to the UI as
#     if it were a contract value.
#   - domain_confidence is passed to the DomainInfo *constructor*, which
#     raised a raw pydantic ValidationError straight past the service's
#     JobIntelligenceValidationError handler - a 500 not only here but on
#     Job Match / ATS Alignment / Gap Analysis, which all generate Job
#     Intelligence on demand.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "confidence", ["super-high", "very high", "", "  ", "0.9", 0.9, None, [], {}]
)
def test_out_of_contract_identity_confidence_falls_back_to_medium(confidence):
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(),
        ai_semantics={
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": "Senior AI Engineer",
            "normalized_title_confidence": confidence,
        },
    )

    # The evidence-backed value itself is still accepted...
    assert result.identity.normalized_title == "AI Engineer"
    # ...only the unrepresentable confidence is replaced.
    assert result.identity.normalized_title_confidence == "medium"


@pytest.mark.parametrize(
    "confidence", ["super-high", "very high", "", "0.9", 0.9, None, [], {}]
)
def test_out_of_contract_domain_confidence_does_not_raise(confidence):
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT + " Machine learning domain.",
        deterministic=_deterministic(),
        ai_semantics={
            "domain": "Machine learning",
            "domain_evidence": "Machine learning",
            "domain_confidence": confidence,
        },
    )

    assert result.domain.value == "Machine learning"
    assert result.domain.confidence == "medium"


@pytest.mark.parametrize(
    ("returned", "expected"),
    [("high", "high"), ("High", "high"), ("  LOW  ", "low"), ("Medium", "medium")],
)
def test_valid_confidence_is_accepted_case_insensitively(returned, expected):
    result = build_job_intelligence_result(
        job_id="job-1",
        analysis_version="1.0",
        raw_title="Senior AI Engineer",
        raw_text=RAW_TEXT,
        deterministic=_deterministic(),
        ai_semantics={
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": "Senior AI Engineer",
            "normalized_title_confidence": returned,
        },
    )

    assert result.identity.normalized_title_confidence == expected
