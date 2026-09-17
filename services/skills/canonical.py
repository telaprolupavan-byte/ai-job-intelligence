"""Canonical skill identity/normalization.

This module is the single source of truth for what a "skill" is across
AJI: resume deterministic analysis, resume evidence adapters, job
requirement extraction, and future Job Intelligence / ATS Alignment work
all resolve skill text through this module instead of maintaining their
own vocabularies.

Two vocabularies existed previously (services/job_matching/skill_normalizer
and apps/api/services/resume_ai/deterministic's SKILL_CATALOG) and had
started to drift: e.g. the resume-side catalog had no alias for
"Python 3"/"python3", and "genai"/"generative ai"/"llm"/"llms"/
"large language models" were tracked as independent, un-related skills
instead of one canonical identity. This module merges both into one
registry.

This module intentionally has no dependency on apps.api or on
services.job_matching, so it can be imported from either side without
creating a circular import.
"""

from __future__ import annotations

import re


# Canonical skill name -> additional surface forms (aliases) that should
# resolve to it. The canonical name itself is always a valid surface form
# and does not need to be repeated here.
CANONICAL_SKILLS: dict[str, frozenset[str]] = {
    # Programming languages
    "python": frozenset({"python 3", "python3", "py", "python programming"}),
    "java": frozenset(),
    "javascript": frozenset({"js"}),
    "typescript": frozenset({"ts"}),
    "c++": frozenset(),
    "sql": frozenset(),
    "r": frozenset(),
    "go": frozenset(),
    "rust": frozenset(),

    # ML / data libraries and frameworks
    "pytorch": frozenset(),
    "tensorflow": frozenset(),
    "scikit-learn": frozenset(),
    "pandas": frozenset(),
    "numpy": frozenset(),
    "xgboost": frozenset(),
    "spark": frozenset(),
    "hadoop": frozenset(),

    # Cloud
    "aws": frozenset({"amazon web services"}),
    "azure": frozenset({"microsoft azure"}),
    "gcp": frozenset({"google cloud platform", "google cloud"}),

    # Infra / tooling
    "docker": frozenset(),
    "kubernetes": frozenset({"k8s"}),
    "terraform": frozenset(),
    "jenkins": frozenset(),
    "github actions": frozenset(),
    "git": frozenset(),
    "linux": frozenset(),

    # Web frameworks
    "fastapi": frozenset(),
    "flask": frozenset(),
    "django": frozenset(),
    "react": frozenset({"react.js", "reactjs"}),
    "next.js": frozenset(),
    "node.js": frozenset(),

    # ML / AI concepts
    "machine learning": frozenset({"ml"}),
    "deep learning": frozenset(),
    "artificial intelligence": frozenset({"ai"}),
    "generative ai": frozenset({"genai"}),
    "llm": frozenset(
        {"llms", "large language model", "large language models"}
    ),
    "nlp": frozenset({"natural language processing"}),
    "computer vision": frozenset(),
    "rag": frozenset({"retrieval augmented generation"}),
    "langchain": frozenset(),
    "transformers": frozenset(),
    "hugging face": frozenset(),
    "mlops": frozenset(),
    "model deployment": frozenset(),
    "model serving": frozenset(),

    # Data
    "data science": frozenset(),
    "data engineering": frozenset(),
    "data analysis": frozenset(),

    # Databases / APIs
    "postgresql": frozenset({"postgres", "postgres db", "postgres database"}),
    "mysql": frozenset(),
    "mongodb": frozenset({"mongo", "mongo db"}),
    "redis": frozenset(),
    "graphql": frozenset(),
    "rest api": frozenset({"restful api", "restful apis", "rest apis"}),
    "microservices": frozenset(),
}


# Surface forms too short/ambiguous to safely search for in free-form
# prose (e.g. "ai" and "ml" appear inside many unrelated words/acronyms).
# They remain valid inputs to normalize_skill() when a skill is already
# explicitly/structurally given (e.g. a job posting's tagged skill list),
# just excluded from free-text scanning.
AMBIGUOUS_SURFACE_FORMS: frozenset[str] = frozenset({"ai", "ml", "js", "ts", "py"})


def _build_skill_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}

    for canonical, extra_aliases in CANONICAL_SKILLS.items():
        aliases[canonical] = canonical

        for alias in extra_aliases:
            aliases[alias] = canonical

    return aliases


# Flat surface-form -> canonical-name lookup, derived from CANONICAL_SKILLS.
SKILL_ALIASES: dict[str, str] = _build_skill_aliases()


def _build_search_terms() -> list[str]:
    terms = {
        surface_form
        for surface_form in SKILL_ALIASES
        if surface_form not in AMBIGUOUS_SURFACE_FORMS
    }

    return sorted(terms, key=len, reverse=True)


# All known surface forms safe to search for in free text (ambiguous short
# forms excluded), longest first so multi-word phrases are matched before
# any shorter substring alias.
SKILL_SEARCH_TERMS: list[str] = _build_search_terms()


def _compile_alias_pattern(surface_forms: frozenset[str] | set[str]) -> re.Pattern[str]:
    ordered = sorted(surface_forms, key=len, reverse=True)
    alternation = "|".join(re.escape(form) for form in ordered)

    return re.compile(
        rf"(?<![a-z0-9])(?:{alternation})(?![a-z0-9])",
        re.IGNORECASE,
    )


def _build_skill_patterns() -> dict[str, re.Pattern[str]]:
    return {
        canonical: _compile_alias_pattern({canonical, *extra_aliases})
        for canonical, extra_aliases in CANONICAL_SKILLS.items()
    }


# Canonical skill -> compiled pattern matching any of its surface forms.
_SKILL_PATTERNS: dict[str, re.Pattern[str]] = _build_skill_patterns()


def normalize_skill(skill: str) -> str:
    """
    Convert a skill into its canonical representation.

    Unknown skills are normalized conservatively (case/whitespace only)
    rather than being mapped to a potentially incorrect known skill.
    """
    if not isinstance(skill, str):
        raise TypeError("skill must be a string")

    normalized = re.sub(r"\s+", " ", skill.strip().lower())

    if not normalized:
        return ""

    return SKILL_ALIASES.get(normalized, normalized)


def normalize_skills(skills: list[str]) -> list[str]:
    """
    Normalize a collection of skills and remove duplicates, preserving
    the order in which each canonical skill first appears.
    """
    normalized: list[str] = []
    seen: set[str] = set()

    for skill in skills:
        canonical = normalize_skill(skill)

        if canonical and canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)

    return normalized


def find_skills(text: str) -> list[str]:
    """
    Detect canonical skills present in free-form text.

    A canonical skill is included if the text contains that skill's
    canonical name OR any of its known aliases as a whole word/phrase
    (case-insensitive). This does not infer skills that are not
    explicitly present in the text, and ambiguous short forms (e.g. "ai",
    "ml") are intentionally never used for free-text scanning.

    Returns canonical skill names only, sorted alphabetically.
    """
    if not text:
        return []

    found = [
        canonical
        for canonical, pattern in _SKILL_PATTERNS.items()
        if pattern.search(text)
    ]

    return sorted(found)


def count_skill_mentions(text: str, canonical_skill: str) -> int:
    """
    Count occurrences of a canonical skill in text, counting a match on
    the canonical name or any of its aliases (e.g. "Python 3" counts as
    a mention of "python").

    Unknown canonical skills fall back to a literal, alias-free search so
    arbitrary/custom skill strings still behave sensibly.
    """
    if not text:
        return 0

    pattern = _SKILL_PATTERNS.get(canonical_skill)

    if pattern is None:
        pattern = _compile_alias_pattern({canonical_skill})

    return len(pattern.findall(text))
