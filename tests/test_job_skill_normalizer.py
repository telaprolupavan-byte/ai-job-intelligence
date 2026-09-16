import pytest

from services.job_matching.skill_normalizer import (
    normalize_skill,
    normalize_skills,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Python", "python"),
        ("PYTHON", "python"),
        ("Python 3", "python"),
        ("python3", "python"),
        ("JS", "javascript"),
        ("JavaScript", "javascript"),
        ("Postgres", "postgresql"),
        ("PostgreSQL", "postgresql"),
        ("Mongo DB", "mongodb"),
        ("RESTful APIs", "rest api"),
        ("K8s", "kubernetes"),
        ("Amazon Web Services", "aws"),
        ("Microsoft Azure", "azure"),
        ("Google Cloud Platform", "gcp"),
        ("ML", "machine learning"),
        ("GenAI", "generative ai"),
        ("LLMs", "llm"),
    ],
)
def test_normalize_skill_aliases(raw: str, expected: str):
    assert normalize_skill(raw) == expected


def test_unknown_skill_is_normalized_conservatively():
    assert normalize_skill("LangChain") == "langchain"


def test_whitespace_is_normalized():
    assert normalize_skill("  PostgreSQL   ") == "postgresql"


def test_empty_skill():
    assert normalize_skill("   ") == ""


def test_skills_are_normalized_and_deduplicated():
    skills = [
        "Python",
        "python 3",
        "PYTHON",
        "Postgres",
        "PostgreSQL",
    ]

    assert normalize_skills(skills) == [
        "python",
        "postgresql",
    ]


def test_similar_but_different_skills_are_not_merged():
    assert normalize_skill("Java") == "java"
    assert normalize_skill("JavaScript") == "javascript"

    assert normalize_skill("AWS") == "aws"
    assert normalize_skill("Azure") == "azure"

    assert normalize_skill("Python") == "python"
    assert normalize_skill("PyTorch") == "pytorch"