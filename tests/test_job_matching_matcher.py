from services.job_matching.contracts import (
    EvidenceType,
    JobRequirements,
    MatchStatus,
)
from services.job_matching.matcher import (
    match_job_requirements,
    match_skills,
)


def test_match_skills_identifies_matched_and_missing():
    result = match_skills(
        required_skills=["Python", "AWS", "Docker"],
        resume_skills=["Python", "AWS"],
    )

    assert len(result) == 3

    assert result[0].skill == "python"
    assert result[0].status == MatchStatus.MATCHED
    assert result[0].evidence_type == EvidenceType.EXPLICIT

    assert result[1].skill == "aws"
    assert result[1].status == MatchStatus.MATCHED

    assert result[2].skill == "docker"
    assert result[2].status == MatchStatus.MISSING
    assert result[2].evidence_type == EvidenceType.NONE


def test_match_skills_uses_skill_aliases():
    result = match_skills(
        required_skills=["JavaScript", "PostgreSQL"],
        resume_skills=["JS", "Postgres"],
    )

    assert result[0].status == MatchStatus.MATCHED
    assert result[1].status == MatchStatus.MATCHED


def test_match_skills_does_not_infer_missing_skill():
    result = match_skills(
        required_skills=["Python"],
        resume_skills=["JavaScript"],
    )

    assert result[0].status == MatchStatus.MISSING
    assert result[0].evidence_type == EvidenceType.NONE
    assert result[0].evidence is None


def test_must_have_and_preferred_are_separate():
    requirements = JobRequirements(
        must_have_skills=["Python", "AWS"],
        preferred_skills=["Docker"],
    )

    must_have, preferred = match_job_requirements(
        requirements,
        ["Python", "Docker"],
    )

    assert len(must_have) == 2
    assert len(preferred) == 1

    assert must_have[0].status == MatchStatus.MATCHED
    assert must_have[1].status == MatchStatus.MISSING

    assert preferred[0].status == MatchStatus.MATCHED