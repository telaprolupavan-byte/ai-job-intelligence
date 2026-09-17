from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from services.job_matching.contracts import MatchStatus
from services.job_matching.extractor import build_job_requirements
from services.job_matching.matcher import match_job_requirements_with_evidence
from services.job_matching.resume_adapter import (
    build_resume_evidence_from_analysis,
)


def test_job_and_resume_skill_extraction_share_one_canonical_identity():
    """
    A job posting written with one surface form of a skill ("Python 3")
    must match a resume written with a different surface form of the same
    skill ("Python programming"), because both sides resolve through the
    same canonical skill vocabulary.
    """

    resume_text = """
    EXPERIENCE
    - Delivered a GenAI feature using Python programming and PyTorch.

    SKILLS
    Python, PyTorch
    """

    job_requirements_text = (
        "Requirements: 2+ years with Python 3 and PyTorch. "
        "Nice to have: GenAI experience."
    )

    resume_analysis = analyze_resume_deterministically(resume_text)
    resume_evidence = build_resume_evidence_from_analysis(resume_analysis)

    job_requirements = build_job_requirements(
        must_have_text=job_requirements_text,
    )

    # Both sides must have resolved to the same canonical skill names.
    assert "python" in job_requirements.must_have_skills
    assert "pytorch" in job_requirements.must_have_skills
    assert "python" in resume_evidence.skills
    assert "pytorch" in resume_evidence.skills

    must_have_matches, _ = match_job_requirements_with_evidence(
        requirements=job_requirements,
        resume_evidence=resume_evidence,
    )

    matched_skills = {
        evidence.skill: evidence.status
        for evidence in must_have_matches
    }

    assert matched_skills["python"] == MatchStatus.MATCHED
    assert matched_skills["pytorch"] == MatchStatus.MATCHED


def test_job_requirement_alias_matches_resume_alias_for_generative_ai():
    resume_text = """
    EXPERIENCE
    - Built an LLM-powered assistant using generative AI techniques.

    SKILLS
    LLMs
    """

    resume_analysis = analyze_resume_deterministically(resume_text)
    resume_evidence = build_resume_evidence_from_analysis(resume_analysis)

    job_requirements = build_job_requirements(
        must_have_text="Requires GenAI and LLM experience.",
    )

    assert "generative ai" in job_requirements.must_have_skills
    assert "llm" in job_requirements.must_have_skills

    must_have_matches, _ = match_job_requirements_with_evidence(
        requirements=job_requirements,
        resume_evidence=resume_evidence,
    )

    matched_skills = {
        evidence.skill: evidence.status
        for evidence in must_have_matches
    }

    assert matched_skills["llm"] == MatchStatus.MATCHED
