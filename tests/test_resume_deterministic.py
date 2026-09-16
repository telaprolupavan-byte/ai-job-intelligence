from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)


def test_resume_deterministic_analysis():
    resume = """
    John Doe
    john@example.com
    555-123-4567
    https://linkedin.com/in/johndoe

    SUMMARY
    AI/ML Engineer with experience building production systems.

    EXPERIENCE
    AI Engineer
    - Built Python machine learning pipelines processing 2M records.
    - Reduced inference latency by 35%.
    - Worked on various data science projects.

    SKILLS
    Python, PyTorch, AWS, Docker, Kubernetes

    PROJECTS
    - Developed an LLM application using Python and AWS.

    EDUCATION
    Master of Science in Computer Information Sciences
    """

    result = analyze_resume_deterministically(resume)

    assert result.word_count > 0
    assert result.character_count > 0

    assert "john@example.com" in result.emails
    assert len(result.urls) == 1

    assert any(
        section.name == "experience"
        for section in result.sections
    )

    assert any(
        bullet.has_quantification
        for bullet in result.bullets
    )

    assert any(
        item["phrase"] == "worked on"
        for item in result.weak_language
    )

    assert any(
        skill.lower() == "python"
        for skill in result.skills
    )


def test_deterministic_analysis_does_not_treat_contact_numbers_as_metrics():
    result = analyze_resume_deterministically(
        """
        Jane Doe
        jane@example.com
        555-123-4567
        EXPERIENCE
        - Built internal tools.
        """
    )

    assert result.quantified_evidence == []
    assert result.bullets[0].has_quantification is False


def test_deterministic_analysis_handles_empty_and_short_input():
    empty_result = analyze_resume_deterministically("")
    short_result = analyze_resume_deterministically("Python")

    assert empty_result.word_count == 0
    assert empty_result.sections == []
    assert empty_result.bullets == []
    assert short_result.skills == ["python"]
    assert short_result.structural_findings


def test_skill_evidence_distinguishes_skills_only_from_demonstrated():
    result = analyze_resume_deterministically(
        """
        SKILLS
        Python, Rust
        EXPERIENCE
        - Built Python services.
        """
    )

    assert result.skill_evidence["python"]["status"] == "demonstrated"
    assert result.skill_evidence["rust"]["status"] == "skills_only"