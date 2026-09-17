from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)


def test_deterministic_skill_extraction_uses_canonical_skills():
    resume = """
    SUMMARY
    Engineer.

    EXPERIENCE
    - Built pipelines using Python 3 and PyTorch.

    SKILLS
    Python, GenAI, LLMs
    """

    result = analyze_resume_deterministically(resume)

    # "GenAI"/"LLMs" and "Python 3" must resolve to the same canonical
    # identity as "generative ai" / "llm" / "python" instead of being
    # tracked as separate, unrelated skills.
    assert result.skills == sorted(set(result.skills))
    assert "python" in result.skills
    assert "generative ai" in result.skills
    assert "llm" in result.skills
    assert "genai" not in result.skills
    assert "llms" not in result.skills


def test_deterministic_evidence_counts_alias_variants_as_the_same_skill():
    resume = """
    EXPERIENCE
    - Shipped a production service in Python 3 with measurable impact.

    SKILLS
    Python
    """

    result = analyze_resume_deterministically(resume)

    python_evidence = result.skill_evidence["python"]

    # "Python 3" in Experience must count as a demonstrated mention of
    # "python", not be invisible to skill evidence because it is not a
    # literal match for the canonical name.
    assert python_evidence["status"] == "demonstrated"
    assert python_evidence["demonstrated_mentions"] >= 1


def test_deterministic_skills_only_alias_variants_are_not_fabricated_as_demonstrated():
    resume = """
    SKILLS
    GenAI, LLMs
    """

    result = analyze_resume_deterministically(resume)

    assert result.skill_evidence["generative ai"]["status"] == "skills_only"
    assert result.skill_evidence["llm"]["status"] == "skills_only"
