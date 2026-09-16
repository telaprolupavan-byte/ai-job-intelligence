from services.job_matching.contracts import (
    EvidenceType,
    MatchStatus,
    SkillEvidence,
)
from services.job_matching.scorer import build_match_result


def evidence(skill: str, status: MatchStatus) -> SkillEvidence:
    return SkillEvidence(
        skill=skill,
        status=status,
        evidence_type=(
            EvidenceType.EXPLICIT
            if status == MatchStatus.MATCHED
            else EvidenceType.NONE
        ),
    )


def test_build_match_result_totals_components():
    result = build_match_result(
        must_have_matches=[
            evidence("python", MatchStatus.MATCHED),
            evidence("aws", MatchStatus.MISSING),
        ],
        preferred_matches=[
            evidence("docker", MatchStatus.MATCHED),
            evidence("kubernetes", MatchStatus.MISSING),
        ],
        experience_score=16,
        role_score=12,
        location_score=10,
        employment_score=5,
    )

    assert result.score == 68.0


def test_match_result_contains_explainable_components():
    result = build_match_result(
        must_have_matches=[
            evidence("python", MatchStatus.MATCHED),
        ],
        preferred_matches=[],
        experience_score=20,
        role_score=15,
        location_score=10,
        employment_score=5,
    )

    assert len(result.components) == 6

    assert result.components[0].name == "must_have_requirements"
    assert result.components[0].max_score == 35

    assert result.components[2].name == "experience"
    assert result.components[2].max_score == 20


def test_match_result_exposes_skill_gaps():
    result = build_match_result(
        must_have_matches=[
            evidence("python", MatchStatus.MATCHED),
            evidence("docker", MatchStatus.MISSING),
        ],
        preferred_matches=[],
        experience_score=20,
        role_score=15,
        location_score=10,
        employment_score=5,
    )

    assert result.skill_gaps == ["docker"]
    assert "Matches required skill: python" in result.strengths