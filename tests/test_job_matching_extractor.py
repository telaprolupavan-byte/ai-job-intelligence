from services.job_matching.extractor import (
    build_job_requirements,
    extract_experience_requirements,
    extract_job_skills,
    split_preferred_section,
)


def test_extract_explicit_experience_requirement():
    requirements = extract_experience_requirements(
        "3+ years of experience developing machine learning applications"
    )

    assert len(requirements) == 1
    assert requirements[0].minimum_years == 3
    assert requirements[0].maximum_years is None


def test_extract_multiple_experience_requirements():
    requirements = extract_experience_requirements(
        "5 years of experience with Python and 2 years of experience with AWS"
    )

    assert len(requirements) == 2
    assert requirements[0].minimum_years == 5
    assert requirements[1].minimum_years == 2


def test_ambiguous_experience_is_not_guessed():
    requirements = extract_experience_requirements(
        "Experience with machine learning is required"
    )

    assert requirements == []


def test_build_job_requirements_normalizes_skills():
    requirements = build_job_requirements(
        must_have_skills=[
            "Python",
            "Postgres",
            "K8s",
        ],
        preferred_skills=[
            "AWS",
            "Docker",
        ],
    )

    assert requirements.must_have_skills == [
        "python",
        "postgresql",
        "kubernetes",
    ]

    assert requirements.preferred_skills == [
        "aws",
        "docker",
    ]


def test_build_job_requirements_separates_required_and_preferred():
    requirements = build_job_requirements(
        must_have_skills=["Python"],
        preferred_skills=["AWS"],
        must_have_text="3+ years of experience with Python",
        preferred_text="2 years of experience with AWS",
    )

    assert requirements.must_have_skills == ["python"]
    assert requirements.preferred_skills == ["aws"]

    assert len(requirements.must_have_experience) == 1
    assert requirements.must_have_experience[0].minimum_years == 3

    assert len(requirements.preferred_experience) == 1
    assert requirements.preferred_experience[0].minimum_years == 2


def test_extract_job_skills_finds_individual_technical_skills():
    text = (
        "We are looking for an engineer with strong Python skills. "
        "Experience with Docker, Machine Learning, and AWS is required. "
        "Familiarity with Kubernetes, FastAPI, SQL, React, PyTorch, and "
        "TensorFlow is a plus."
    )

    skills = extract_job_skills(text)

    assert set(skills) == {
        "python",
        "docker",
        "machine learning",
        "aws",
        "kubernetes",
        "fastapi",
        "sql",
        "react",
        "pytorch",
        "tensorflow",
    }


def test_extract_job_skills_does_not_treat_every_word_as_a_skill():
    text = (
        "We want a collaborative teammate who communicates clearly and "
        "solves problems quickly."
    )

    assert extract_job_skills(text) == []


def test_extract_job_skills_normalizes_aliases():
    text = "Must know K8s, Postgres, and JS."

    skills = extract_job_skills(text)

    assert "kubernetes" in skills
    assert "postgresql" in skills


def test_extract_job_skills_returns_empty_for_no_text():
    assert extract_job_skills("") == []
    assert extract_job_skills(None) == []


def test_split_preferred_section_separates_nice_to_have():
    text = (
        "Requirements: Python and Docker experience required.\n"
        "Nice to have: AWS and Kubernetes experience."
    )

    must_have_text, preferred_text = split_preferred_section(text)

    assert "Python" in must_have_text
    assert "AWS" not in must_have_text
    assert "AWS" in preferred_text


def test_split_preferred_section_without_marker_is_all_must_have():
    text = "Python and Docker experience required."

    must_have_text, preferred_text = split_preferred_section(text)

    assert must_have_text == text
    assert preferred_text == ""


def test_build_job_requirements_extracts_skills_from_job_text():
    requirements = build_job_requirements(
        must_have_text=(
            "Requirements: Python, Docker, Machine Learning, and AWS."
        ),
    )

    assert set(requirements.must_have_skills) == {
        "python",
        "docker",
        "machine learning",
        "aws",
    }


def test_build_job_requirements_splits_must_have_and_preferred_text():
    requirements = build_job_requirements(
        must_have_text="Requires Python and Docker.",
        preferred_text="Nice to have: Kubernetes and AWS.",
    )

    assert set(requirements.must_have_skills) == {"python", "docker"}
    assert set(requirements.preferred_skills) == {"kubernetes", "aws"}


def test_build_job_requirements_does_not_duplicate_must_have_in_preferred():
    requirements = build_job_requirements(
        must_have_text="Requires Python.",
        preferred_text="Python and AWS are a plus.",
    )

    assert requirements.must_have_skills == ["python"]
    assert requirements.preferred_skills == ["aws"]