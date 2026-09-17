"""Canonical skill identity/normalization, shared across resume analysis,
job matching, and future Job Intelligence / ATS Alignment work.

See services.skills.canonical for the full documentation.
"""

from services.skills.canonical import (
    AMBIGUOUS_SURFACE_FORMS,
    CANONICAL_SKILLS,
    SKILL_ALIASES,
    SKILL_SEARCH_TERMS,
    count_skill_mentions,
    find_skills,
    normalize_skill,
    normalize_skills,
)

__all__ = [
    "AMBIGUOUS_SURFACE_FORMS",
    "CANONICAL_SKILLS",
    "SKILL_ALIASES",
    "SKILL_SEARCH_TERMS",
    "count_skill_mentions",
    "find_skills",
    "normalize_skill",
    "normalize_skills",
]
