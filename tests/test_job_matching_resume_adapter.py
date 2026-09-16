from types import SimpleNamespace

from services.job_matching.contracts import EvidenceType, MatchStatus
from services.job_matching.resume_adapter import (
    build_resume_evidence_from_analysis,
)


def make_analysis(skills: list[str], skill_evidence: dict) -> SimpleNamespace:
    return SimpleNamespace(skills=skills, skill_evidence=skill_evidence)


def test_skills_section_only_is_explicit_not_experience():
    analysis = make_analysis(
        skills=["python"],
        skill_evidence={
            "python": {
                "status": "skills_only",
                "total_mentions": 1,
                "skills_section_mentions": 1,
                "demonstrated_mentions": 0,
            }
        },
    )

    result = build_resume_evidence_from_analysis(analysis)

    assert len(result.evidence) == 1
    entry = result.evidence[0]

    assert entry.skill == "python"
    assert entry.status == MatchStatus.MATCHED
    assert entry.evidence_type == EvidenceType.EXPLICIT
    assert entry.evidence_type != EvidenceType.EXPERIENCE


def test_demonstrated_experience_is_stronger_evidence():
    analysis = make_analysis(
        skills=["python"],
        skill_evidence={
            "python": {
                "status": "demonstrated",
                "total_mentions": 3,
                "skills_section_mentions": 1,
                "demonstrated_mentions": 2,
            }
        },
    )

    result = build_resume_evidence_from_analysis(analysis)

    entry = result.evidence[0]

    assert entry.skill == "python"
    assert entry.status == MatchStatus.MATCHED
    assert entry.evidence_type == EvidenceType.EXPERIENCE


def test_weak_or_no_evidence_is_not_fabricated_as_a_match():
    analysis = make_analysis(
        skills=["python"],
        skill_evidence={
            "python": {
                "status": "weakly_supported",
                "total_mentions": 0,
                "skills_section_mentions": 0,
                "demonstrated_mentions": 0,
            }
        },
    )

    result = build_resume_evidence_from_analysis(analysis)

    entry = result.evidence[0]

    assert entry.status == MatchStatus.UNCERTAIN
    assert entry.status != MatchStatus.MATCHED
    assert entry.evidence_type == EvidenceType.INFERRED


def test_missing_skill_evidence_entry_is_not_fabricated_as_a_match():
    analysis = make_analysis(
        skills=["python"],
        skill_evidence={},
    )

    result = build_resume_evidence_from_analysis(analysis)

    entry = result.evidence[0]

    assert entry.status == MatchStatus.UNCERTAIN


def test_mixed_skills_are_each_represented_by_their_own_evidence_strength():
    analysis = make_analysis(
        skills=["python", "docker", "aws"],
        skill_evidence={
            "python": {
                "status": "demonstrated",
                "demonstrated_mentions": 2,
                "skills_section_mentions": 1,
            },
            "docker": {
                "status": "skills_only",
                "demonstrated_mentions": 0,
                "skills_section_mentions": 1,
            },
            "aws": {
                "status": "weakly_supported",
                "demonstrated_mentions": 0,
                "skills_section_mentions": 0,
            },
        },
    )

    result = build_resume_evidence_from_analysis(analysis)
    by_skill = {entry.skill: entry for entry in result.evidence}

    assert by_skill["python"].evidence_type == EvidenceType.EXPERIENCE
    assert by_skill["docker"].evidence_type == EvidenceType.EXPLICIT
    assert by_skill["aws"].status == MatchStatus.UNCERTAIN

    # The flat skill list is unaffected by evidence strength.
    assert result.skills == ["python", "docker", "aws"]
