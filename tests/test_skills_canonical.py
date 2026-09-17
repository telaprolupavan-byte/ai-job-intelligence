import pytest

from services.skills import (
    count_skill_mentions,
    find_skills,
    normalize_skill,
    normalize_skills,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Python", "python"),
        ("python", "python"),
        ("PYTHON", "python"),
        ("Python 3", "python"),
        ("python3", "python"),
        ("python programming", "python"),
        ("PyTorch", "pytorch"),
        ("pytorch", "pytorch"),
        ("GenAI", "generative ai"),
        ("generative ai", "generative ai"),
        ("LLMs", "llm"),
        ("Large Language Models", "llm"),
    ],
)
def test_canonical_aliases_resolve_to_one_identity(raw: str, expected: str):
    assert normalize_skill(raw) == expected


def test_case_insensitive_and_whitespace_variations_are_equivalent():
    variants = ["Python", "python", "  PYTHON  ", "Python\t3", "python 3"]

    canonical_forms = {normalize_skill(variant) for variant in variants}

    assert canonical_forms == {"python"}


def test_similar_but_distinct_skills_stay_distinct():
    assert normalize_skill("Java") == "java"
    assert normalize_skill("JavaScript") == "javascript"
    assert normalize_skill("Python") != normalize_skill("PyTorch")


def test_unknown_skill_is_normalized_conservatively():
    assert normalize_skill("LangChain") == "langchain"
    assert normalize_skill("SomeBrandNewTool") == "somebrandnewtool"


def test_normalize_skills_deduplicates_aliases_of_the_same_skill():
    skills = [
        "Python",
        "python 3",
        "Python Programming",
        "PyTorch",
        "pytorch",
    ]

    assert normalize_skills(skills) == ["python", "pytorch"]


def test_find_skills_detects_aliases_as_one_canonical_skill():
    text = (
        "Built a GenAI RAG pipeline in Python 3 using PyTorch and "
        "LangChain. Also used generative AI and LLMs elsewhere."
    )

    skills = find_skills(text)

    assert skills == sorted(set(skills)), "find_skills must not return duplicates"
    assert "python" in skills
    assert "pytorch" in skills
    assert "langchain" in skills
    assert "generative ai" in skills
    assert "llm" in skills

    # "genai" and "llms" must never appear as independent skill identities.
    assert "genai" not in skills
    assert "llms" not in skills


def test_find_skills_does_not_match_ambiguous_short_forms():
    text = "We train and maintain our applications daily."

    # "ai"/"ml" style short forms must never be inferred from prose.
    assert find_skills(text) == []


def test_find_skills_returns_empty_for_no_text():
    assert find_skills("") == []
    assert find_skills(None) == []


def test_count_skill_mentions_counts_across_aliases():
    text = "Python 3 experience. Also used python for scripting and Python."

    assert count_skill_mentions(text, "python") == 3


def test_count_skill_mentions_is_case_insensitive():
    text = "PYTHON, Python, python"

    assert count_skill_mentions(text, "python") == 3


def test_count_skill_mentions_unknown_canonical_falls_back_to_literal_search():
    text = "We use CustomInternalTool daily for CustomInternalTool tasks."

    assert count_skill_mentions(text, "custominternaltool") == 2
