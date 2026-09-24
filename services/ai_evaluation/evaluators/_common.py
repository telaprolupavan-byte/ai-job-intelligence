from __future__ import annotations

import re

from services.ai_evaluation.dataset import MatchCase


def normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def same_text(expected: str, actual: str | None) -> bool:
    """Loose equality for short labelled strings (company names,
    responsibilities): one normalized string contains the other."""
    left, right = normalize_text(expected), normalize_text(actual)
    return bool(left and right) and (left in right or right in left)


def satisfied_group_members(case: MatchCase, level: str) -> set[str]:
    """Members of satisfied alternative (OR) groups for one tier: a
    member of such a group that the resume lacks is not a real gap."""
    return {
        member
        for group in case.expected.requirement_groups
        if group.level == level and group.satisfied
        for member in group.members
    }

