from services.job_matching.contracts import (
    EvidenceType,
    MatchStatus,
    SkillEvidence,
)
from services.job_matching.scorer import (
    score_must_have_requirements,
    score_preferred_requirements,
    score_requirement_matches,
)


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


def test_all_requirements_matched():
    matches = [
        evidence("python", MatchStatus.MATCHED),
        evidence("aws", MatchStatus.MATCHED),
    ]

    assert score_requirement_matches(matches, 35) == 35


def test_half_requirements_matched():
    matches = [
        evidence("python", MatchStatus.MATCHED),
        evidence("aws", MatchStatus.MISSING),
    ]

    assert score_requirement_matches(matches, 35) == 17.5


def test_no_requirements_matched():
    matches = [
        evidence("python", MatchStatus.MISSING),
        evidence("aws", MatchStatus.MISSING),
    ]

    assert score_requirement_matches(matches, 35) == 0


def test_uncertain_requirement_receives_no_credit():
    matches = [
        evidence("python", MatchStatus.MATCHED),
        evidence("aws", MatchStatus.UNCERTAIN),
    ]

    assert score_requirement_matches(matches, 35) == 17.5


def test_empty_requirements_receive_full_component_score():
    assert score_must_have_requirements([]) == 35
    assert score_preferred_requirements([]) == 15


def test_must_have_uses_35_point_weight():
    matches = [
        evidence("python", MatchStatus.MATCHED),
        evidence("aws", MatchStatus.MATCHED),
        evidence("docker", MatchStatus.MISSING),
        evidence("postgresql", MatchStatus.MISSING),
    ]

    assert score_must_have_requirements(matches) == 17.5


def test_preferred_uses_15_point_weight():
    matches = [
        evidence("docker", MatchStatus.MATCHED),
        evidence("kubernetes", MatchStatus.MISSING),
    ]

    assert score_preferred_requirements(matches) == 7.5