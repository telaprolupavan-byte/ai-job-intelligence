from services.job_matching.contracts import ExperienceRequirement
from services.job_matching.scorer import (
    score_experience,
    score_role_alignment,
)


def test_experience_meets_requirement():
    requirement = ExperienceRequirement(
        minimum_years=5,
    )

    assert score_experience(
        resume_years=5,
        requirements=[requirement],
        max_score=20,
    ) == 20


def test_experience_exceeds_requirement():
    requirement = ExperienceRequirement(
        minimum_years=5,
    )

    assert score_experience(
        resume_years=7,
        requirements=[requirement],
        max_score=20,
    ) == 20


def test_experience_partial_match():
    requirement = ExperienceRequirement(
        minimum_years=5,
    )

    assert score_experience(
        resume_years=4,
        requirements=[requirement],
        max_score=20,
    ) == 16


def test_unknown_experience_gets_no_credit():
    requirement = ExperienceRequirement(
        minimum_years=5,
    )

    assert score_experience(
        resume_years=None,
        requirements=[requirement],
        max_score=20,
    ) == 0


def test_no_experience_requirement_gets_full_score():
    assert score_experience(
        resume_years=3,
        requirements=[],
        max_score=20,
    ) == 20


def test_exact_role_match():
    assert score_role_alignment(
        job_title="AI Engineer",
        resume_titles=["AI Engineer"],
        max_score=15,
    ) == 15


def test_related_role_match():
    assert score_role_alignment(
        job_title="AI Engineer",
        resume_titles=[
            "Machine Learning Engineer",
            "Software Engineer",
        ],
        max_score=15,
    ) > 0


def test_unrelated_role_match():
    assert score_role_alignment(
        job_title="AI Engineer",
        resume_titles=["Accountant"],
        max_score=15,
    ) == 0