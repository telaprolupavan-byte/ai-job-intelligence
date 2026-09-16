from services.job_matching.contracts import (
    EvidenceType,
    JobMatchResult,
    MatchComponent,
    MatchStatus,
    SkillEvidence,
)


def test_skill_evidence_contract():
    evidence = SkillEvidence(
        skill="Python",
        status=MatchStatus.MATCHED,
        evidence_type=EvidenceType.EXPLICIT,
        evidence="Python listed in technical skills",
    )

    assert evidence.skill == "Python"
    assert evidence.status == MatchStatus.MATCHED
    assert evidence.evidence_type == EvidenceType.EXPLICIT


def test_job_match_result_defaults():
    result = JobMatchResult(
        score=87,
        confidence="high",
    )

    assert result.score == 87
    assert result.confidence == "high"
    assert result.must_have_matches == []
    assert result.must_have_gaps == []
    assert result.preferred_matches == []
    assert result.preferred_gaps == []
    assert result.engine_version == "1.0.0"


def test_match_component():
    component = MatchComponent(
        name="Must-have requirements",
        score=30,
        max_score=35,
        explanation="Most required skills are supported by resume evidence.",
    )

    assert component.score == 30
    assert component.max_score == 35
    assert component.name == "Must-have requirements"