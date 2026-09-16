from services.job_matching.contracts import JobRequirements
from services.job_matching.service import JobMatchingService


def test_service_calculates_complete_match():
    service = JobMatchingService()

    requirements = JobRequirements(
        must_have_skills=[
            "Python",
            "AWS",
            "Docker",
        ],
        preferred_skills=[
            "Kubernetes",
        ],
    )

    result = service.calculate_match(
        job_title="AI Engineer",
        job_requirements=requirements,
        resume_skills=[
            "Python",
            "AWS",
        ],
        resume_years=4,
        resume_titles=[
            "Machine Learning Engineer",
        ],
        job_remote_type="remote",
        job_location=None,
        job_employment_type="full_time",
        preferred_remote_type="remote",
        preferred_employment_type="full_time",
    )

    assert result.score >= 0
    assert result.score <= 100

    assert result.confidence == "high"

    assert "docker" in result.skill_gaps

    assert len(result.components) == 6


def test_service_detects_missing_must_have_skill():
    service = JobMatchingService()

    requirements = JobRequirements(
        must_have_skills=[
            "Python",
            "PyTorch",
        ],
    )

    result = service.calculate_match(
        job_title="ML Engineer",
        job_requirements=requirements,
        resume_skills=[
            "Python",
        ],
    )

    assert result.score >= 0

    assert "pytorch" in result.skill_gaps

    assert len(result.must_have_gaps) == 1


def test_service_handles_sparse_resume():
    service = JobMatchingService()

    requirements = JobRequirements(
        must_have_skills=["Python"],
    )

    result = service.calculate_match(
        job_title="Python Developer",
        job_requirements=requirements,
        resume_skills=[],
    )

    assert result.score >= 0
    assert result.score <= 100

    assert result.confidence == "low"