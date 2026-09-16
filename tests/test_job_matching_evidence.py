from services.job_matching.contracts import EvidenceType, MatchStatus
from services.job_matching.evidence import build_resume_evidence


def test_build_resume_evidence_normalizes_skills():
    result = build_resume_evidence(
        skills=["Python", "PYTHON", "AWS"],
        experience_years=3,
    )

    assert result.skills == ["python", "aws"]
    assert result.experience_years == 3


def test_build_resume_evidence_creates_explicit_evidence():
    result = build_resume_evidence(
        skills=["Python", "AWS"],
    )

    assert len(result.evidence) == 2

    assert result.evidence[0].skill == "python"
    assert result.evidence[0].status == MatchStatus.MATCHED
    assert result.evidence[0].evidence_type == EvidenceType.EXPLICIT


def test_skill_presence_does_not_create_experience_claim():
    result = build_resume_evidence(
        skills=["Python"],
    )

    assert result.experience_years is None