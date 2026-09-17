"""Backward-compatible re-export of the canonical skill normalizer.

The canonical skill vocabulary and normalization logic now live in
services.skills (shared with resume-side deterministic analysis). This
module is kept so existing imports of
`services.job_matching.skill_normalizer` continue to work unchanged.
"""

from services.skills.canonical import (
    SKILL_ALIASES,
    normalize_skill,
    normalize_skills,
)

__all__ = [
    "SKILL_ALIASES",
    "normalize_skill",
    "normalize_skills",
]
