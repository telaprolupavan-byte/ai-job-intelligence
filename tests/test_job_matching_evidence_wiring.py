from types import SimpleNamespace

from services.job_matching.contracts import (
    EvidenceType,
    JobRequirements,
    MatchStatus,
)
from services.job_matching.resume_adapter import (
    build_resume_evidence_from_analysis,
)
from services.job_matching.service import JobMatchingService


def make_analysis(skills: list[str], skill_evidence: dict) -> SimpleNamespace:
    return SimpleNamespace(skills=skills, skill_evidence=skill_evidence)


def _sample_job_requirements() -> JobRequirements:
    return JobRequirements(
        must_have_skills=[
            "Python",
            "Docker",
            "Machine Learning",
            "AWS",
        ],
        preferred_skills=["Kubernetes"],
    )


def _sample_resume_evidence(experience_years: float = 3.0):
    analysis = make_analysis(
        skills=["python", "docker", "aws"],
        skill_evidence={
            "python": {
                "status": "demonstrated",
                "demonstrated_mentions": 2,
                "skills_section_mentions": 1,
            },
            "docker": {
                "status": "demonstrated",
                "demonstrated_mentions": 1,
                "skills_section_mentions": 1,
            },
            "aws": {
                "status": "skills_only",
                "demonstrated_mentions": 0,
                "skills_section_mentions": 1,
            },
        },
    )

    return build_resume_evidence_from_analysis(
        analysis,
        experience_years=experience_years,
    )


def test_skills_section_only_does_not_become_experience_in_final_result():
    resume_evidence = _sample_resume_evidence()

    result = JobMatchingService().calculate_match(
        job_title="AI Engineer",
        job_requirements=_sample_job_requirements(),
        resume_evidence=resume_evidence,
    )

    aws_match = next(
        m for m in result.must_have_matches if m.skill == "aws"
    )

    assert aws_match.status == MatchStatus.MATCHED
    assert aws_match.evidence_type == EvidenceType.EXPLICIT
    assert aws_match.evidence_type != EvidenceType.EXPERIENCE


def test_demonstrated_experience_reaches_final_result():
    resume_evidence = _sample_resume_evidence()

    result = JobMatchingService().calculate_match(
        job_title="AI Engineer",
        job_requirements=_sample_job_requirements(),
        resume_evidence=resume_evidence,
    )

    python_match = next(
        m for m in result.must_have_matches if m.skill == "python"
    )
    docker_match = next(
        m for m in result.must_have_matches if m.skill == "docker"
    )

    assert python_match.evidence_type == EvidenceType.EXPERIENCE
    assert docker_match.evidence_type == EvidenceType.EXPERIENCE


def test_missing_required_skill_is_not_matched():
    resume_evidence = _sample_resume_evidence()

    result = JobMatchingService().calculate_match(
        job_title="AI Engineer",
        job_requirements=_sample_job_requirements(),
        resume_evidence=resume_evidence,
    )

    ml_entries = [
        m for m in result.must_have_matches if m.skill == "machine learning"
    ]
    assert ml_entries == []

    ml_gap = next(
        m for m in result.must_have_gaps if m.skill == "machine learning"
    )
    assert ml_gap.status == MatchStatus.MISSING
    assert ml_gap.evidence_type == EvidenceType.NONE
    assert "machine learning" in result.skill_gaps


def test_mixed_evidence_scenario_produces_expected_final_result():
    resume_evidence = _sample_resume_evidence()

    result = JobMatchingService().calculate_match(
        job_title="AI Engineer",
        job_requirements=_sample_job_requirements(),
        resume_evidence=resume_evidence,
        resume_titles=["AI Engineer"],
        job_remote_type="remote",
        job_employment_type="full_time",
        preferred_remote_type="remote",
        preferred_employment_type="full_time",
    )

    matched_skills = {m.skill for m in result.must_have_matches}
    gap_skills = {m.skill for m in result.must_have_gaps}
    preferred_gap_skills = {m.skill for m in result.preferred_gaps}

    assert matched_skills == {"python", "docker", "aws"}
    assert gap_skills == {"machine learning"}
    assert preferred_gap_skills == {"kubernetes"}

    # 3 of 4 must-have skills matched, out of the existing 35-point weight.
    must_have_component = next(
        c for c in result.components if c.name == "must_have_requirements"
    )
    assert must_have_component.max_score == 35
    assert must_have_component.score == round((3 / 4) * 35, 2)

    preferred_component = next(
        c for c in result.components if c.name == "preferred_requirements"
    )
    assert preferred_component.max_score == 15
    assert preferred_component.score == 0

    assert 0 <= result.score <= 100
    assert len(result.components) == 6


def test_missing_skill_does_not_receive_credit_despite_flat_skill_presence():
    """
    A skill only reachable via a flat name list (no real evidence) must not
    grant full must-have credit for a skill the analyzer never detected.
    """
    resume_evidence = _sample_resume_evidence()

    result = JobMatchingService().calculate_match(
        job_title="AI Engineer",
        job_requirements=_sample_job_requirements(),
        resume_evidence=resume_evidence,
    )

    must_have_component = next(
        c for c in result.components if c.name == "must_have_requirements"
    )

    assert must_have_component.score < must_have_component.max_score


def test_existing_six_components_and_weights_are_unchanged():
    resume_evidence = _sample_resume_evidence()

    result = JobMatchingService().calculate_match(
        job_title="AI Engineer",
        job_requirements=_sample_job_requirements(),
        resume_evidence=resume_evidence,
    )

    weights_by_name = {
        component.name: component.max_score
        for component in result.components
    }

    assert weights_by_name == {
        "must_have_requirements": 35,
        "preferred_requirements": 15,
        "experience": 20,
        "role_alignment": 15,
        "location": 10,
        "employment_type": 5,
    }


def test_flat_resume_skills_path_still_works_without_resume_evidence():
    """Backward-compatible path used before evidence wiring must still work."""
    result = JobMatchingService().calculate_match(
        job_title="AI Engineer",
        job_requirements=_sample_job_requirements(),
        resume_skills=["Python", "Docker", "AWS"],
    )

    matched_skills = {m.skill for m in result.must_have_matches}
    assert matched_skills == {"python", "docker", "aws"}

    # The legacy flat-list path has no rich evidence, so it stays EXPLICIT.
    python_match = next(
        m for m in result.must_have_matches if m.skill == "python"
    )
    assert python_match.evidence_type == EvidenceType.EXPLICIT
