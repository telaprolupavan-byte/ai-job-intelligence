"""Applying a General Resume review (AJI-027): pure, DB-free, AI-free.

The rules, all enforced here and server-side:

- **Only stored improvements can be decided.** Every decision must name
  an `improvement_id` from the stored assessment; its `suggestion_type`
  comes from that stored row, never from the request.
- **The user writes every word.** An approval requires non-empty
  `user_content`, and `build_refined_content` writes only that text plus
  a bullet marker or a fixed, analyzer-recognized section heading. No
  explanation, guidance, evidence or AI text is ever written.
- **`ADD_IF_TRUE` requires truth confirmation**, and **`ADVISORY`
  improvements cannot be approved** (they are not text changes).
- **Rejecting everything is allowed** (a Product Owner decision): the
  review is recorded and no version is created.
- **The parent is never modified.** The result is a new string; every
  line not being replaced is kept exactly as it was.
- **Duplicates are prevented** by `compute_review_fingerprint`, backed by
  a database unique constraint.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from apps.api.services.general_resume.contracts import Improvement
from apps.api.services.general_resume.improvements import BULLET_PATTERN
from apps.api.services.resume_improvement.engine import sanitize_user_content


ENGINE_VERSION = "1.0"

VERSION_SOURCE = "general_improvement"

# Each must stay an exact alias in
# apps/api/services/resume_ai/deterministic.py's SECTION_ALIASES, so the
# analyzer recognizes appended content as its own section rather than as
# part of whatever section the parent ended with. A test pins this.
SECTION_HEADINGS = {
    "experience": "Professional Experience",
    "education": "Education",
    "skills": "Skills",
}

BULLET_PREFIX = "- "


class ReviewValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedDecision:
    improvement: Improvement
    action: str
    truth_confirmed: bool
    applied_text: str | None


def validate_review_decisions(
    *,
    decisions: list[dict],
    improvements_by_id: dict[str, Improvement],
) -> list[ValidatedDecision]:
    """Apply every review rule. Raises on the first violation: a decision
    set with one unauthorized approval is not one the user authorized."""
    seen: set[str] = set()
    validated: list[ValidatedDecision] = []

    for decision in decisions:
        identifier = (decision.get("improvement_id") or "").strip()
        improvement = improvements_by_id.get(identifier)

        if improvement is None:
            raise ReviewValidationError(
                "unknown_improvement",
                "Every decision must reference an improvement from this "
                "assessment.",
            )

        if identifier in seen:
            raise ReviewValidationError(
                "duplicate_decision",
                f'"{improvement.title}" was decided more than once.',
            )

        seen.add(identifier)
        action = decision.get("action")

        if action == "reject":
            validated.append(
                ValidatedDecision(
                    improvement=improvement,
                    action="reject",
                    truth_confirmed=False,
                    applied_text=None,
                )
            )
            continue

        if action != "approve":
            raise ReviewValidationError(
                "invalid_action",
                f"Unsupported decision '{action}'.",
            )

        if improvement.suggestion_type == "ADVISORY":
            raise ReviewValidationError(
                "advisory_not_applicable",
                f'"{improvement.title}" cannot be applied as a text change. '
                "Reject it, or fix it by uploading a new version.",
            )

        content = sanitize_user_content(decision.get("user_content"))

        if not content:
            raise ReviewValidationError(
                "content_required",
                f'Approving "{improvement.title}" requires your own '
                "wording. NERO never writes resume content for you.",
            )

        truth_confirmed = bool(decision.get("truth_confirmed"))

        if improvement.suggestion_type == "ADD_IF_TRUE" and not truth_confirmed:
            raise ReviewValidationError(
                "truth_confirmation_required",
                f'"{improvement.title}" can only be applied if you confirm '
                "what you wrote is accurate.",
            )

        validated.append(
            ValidatedDecision(
                improvement=improvement,
                action="approve",
                truth_confirmed=truth_confirmed,
                applied_text=content,
            )
        )

    return validated


def _strip_marker(line: str) -> str:
    return BULLET_PATTERN.sub("", line).strip()


def build_refined_content(
    *,
    parent_content: str,
    decisions: list[ValidatedDecision],
) -> str:
    """The child version's text.

    - A bullet approval replaces every line whose stripped text is that
      improvement's `anchor_line` with the user's line(s), keeping the
      original indentation and bullet marker.
    - A contact approval is inserted after the first line (the name).
    - A missing section or skill approval is appended under a recognized
      heading (skills in context go under an experience heading).

    Raises `ReviewValidationError("stale_improvement")` if an anchored
    line is not in the parent - the parent is immutable, so this only
    happens if an assessment is paired with the wrong version.
    """
    approved = [d for d in decisions if d.action == "approve"]

    if not approved:
        return parent_content

    replacements: dict[str, list[str]] = {}
    contact_lines: list[str] = []
    blocks: dict[str, list[str]] = {"experience": [], "education": [], "skills": []}

    for decision in approved:
        improvement = decision.improvement
        user_lines = [
            _strip_marker(line) or line
            for line in decision.applied_text.split("\n")
        ]

        if improvement.kind == "bullet":
            replacements[improvement.anchor_line] = user_lines
        elif improvement.kind == "missing_contact":
            contact_lines.extend(user_lines)
        elif improvement.kind == "missing_section":
            blocks[improvement.target].extend(user_lines)
        elif improvement.kind == "skill_not_demonstrated":
            blocks["experience"].extend(user_lines)

    raw_lines = (
        parent_content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    )
    output: list[str] = []
    applied: set[str] = set()

    for raw in raw_lines:
        stripped = raw.strip()
        replacement = replacements.get(stripped)

        if replacement is None:
            output.append(raw)
            continue

        applied.add(stripped)
        indent = raw[: len(raw) - len(raw.lstrip())]
        marker_match = BULLET_PATTERN.match(stripped)
        marker = marker_match.group(0).strip() if marker_match else "-"

        for line in replacement:
            output.append(f"{indent}{marker} {line}")

    if set(replacements) - applied:
        raise ReviewValidationError(
            "stale_improvement",
            "A line this review refers to is no longer in the resume.",
        )

    if contact_lines:
        insert_at = next(
            (index + 1 for index, line in enumerate(output) if line.strip()),
            0,
        )
        output[insert_at:insert_at] = contact_lines

    text = "\n".join(output).rstrip()

    for section in ("experience", "education", "skills"):
        lines = blocks[section]

        if not lines:
            continue

        prefix = BULLET_PREFIX if section == "experience" else ""
        block = [SECTION_HEADINGS[section]] + [f"{prefix}{line}" for line in lines]
        text = f"{text}\n\n" + "\n".join(block)

    return text + "\n"


def compute_review_fingerprint(
    *,
    assessment_id: str,
    parent_resume_version_id: str,
    decisions: list[ValidatedDecision],
) -> str:
    """Stable over what the review records: which assessment and parent,
    every approved improvement's confirmed user text, and every rejected
    improvement id (rejections are persisted, so they are part of what a
    review *is*). Order-independent."""
    payload = {
        "assessment_id": assessment_id,
        "parent_resume_version_id": parent_resume_version_id,
        "approved": sorted(
            (
                {
                    "improvement_id": d.improvement.improvement_id,
                    "suggestion_type": d.improvement.suggestion_type,
                    "truth_confirmed": d.truth_confirmed,
                    "applied_text": d.applied_text,
                }
                for d in decisions
                if d.action == "approve"
            ),
            key=lambda item: item["improvement_id"],
        ),
        "rejected": sorted(
            d.improvement.improvement_id
            for d in decisions
            if d.action == "reject"
        ),
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def next_refined_version_name(existing_names: list[str]) -> str:
    """"Refined N", numbered separately from uploads and from AJI-021's
    "Improved N" versions."""
    used = set()

    for name in existing_names:
        match = re.fullmatch(r"Refined (\d+)", name.strip())

        if match:
            used.add(int(match.group(1)))

    number = 1

    while number in used:
        number += 1

    return f"Refined {number}"
