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