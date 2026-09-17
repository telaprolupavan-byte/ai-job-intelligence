import pytest
from pydantic import ValidationError

from apps.api.services.job_intelligence.contracts import (
    CompensationInfo,
    JobIdentity,
    JobIntelligenceResult,
    LocationInfo,
    SkillRequirement,
)


def _base_result(**overrides) -> dict:
    defaults = dict(
        analysis_version="1.0",
        job_id="job-1",
        identity=JobIdentity(original_title="AI Engineer"),
        employment={"employment_type": "unknown"},
        location=LocationInfo(),
    )
    defaults.update(overrides)
    return defaults


def test_valid_result_round_trips_through_json():
    result = JobIntelligenceResult(**_base_result())
    payload = result.model_dump(mode="json")
    rehydrated = JobIntelligenceResult.model_validate(payload)

    assert rehydrated.identity.original_title == "AI Engineer"


def test_skill_requirement_rejects_invalid_level():
    with pytest.raises(ValidationError):
        SkillRequirement(
            canonical_skill="python",
            level="mandatory",  # not a valid Level
            evidence_text="Python required",
        )


def test_skill_requirement_rejects_empty_evidence():
    with pytest.raises(ValidationError):
        SkillRequirement(
            canonical_skill="python",
            level="required",
            evidence_text="",
        )


def test_skill_requirement_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        SkillRequirement(
            canonical_skill="python",
            level="required",
            evidence_text="Python required",
            confidence="certain",  # not high/medium/low
        )


def test_employment_type_rejects_unknown_enum_value():
    with pytest.raises(ValidationError):
        JobIntelligenceResult(
            **_base_result(employment={"employment_type": "gig"})
        )


def test_compensation_defaults_to_unknown_period():
    compensation = CompensationInfo()
    assert compensation.period == "unknown"
    assert compensation.salary_min is None


def test_job_identity_requires_original_title():
    with pytest.raises(ValidationError):
        JobIdentity(original_title="")
