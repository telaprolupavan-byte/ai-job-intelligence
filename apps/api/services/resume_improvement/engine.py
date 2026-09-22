"""Resume Improvement (AJI-021) deterministic core.

DB-free, AI-free, and the module that owns every safety rule the ticket
requires. There is no AI stage anywhere in Resume Improvement: the only
new text it ever produces is a fixed section heading and a `- ` bullet
prefix. Everything else is either the user's own words or data copied
verbatim from an existing `GapAnalysis` / `AtsAlignmentResult` row.

The rules, and where each is enforced:

- **Approval is mandatory.** `validate_decisions` rejects a submission
  with zero approvals (`no_approvals`). Nothing is ever applied because
  the user merely viewed a suggestion.
- **`ADD_IF_TRUE` requires explicit truth confirmation.**
  `validate_decisions` rejects an approved `ADD_IF_TRUE` decision whose
  `truth_confirmed` is not `True` (`truth_confirmation_required`). The
  suggestion type is passed in from the stored Gap Analysis gap by the
  caller, never from the request body, so relabelling a gap client-side
  cannot bypass this.
- **Nothing is fabricated.** Every approved decision must carry
  non-empty `user_content` (`content_required`), and
  `build_improved_content` writes *only* that text. The requirement
  text, the JD evidence, and the Gap Analysis suggestion string - the
  three places an unverified claim could otherwise come from - are
  never written into a resume version.
- **The original is never overwritten.** `build_improved_content`
  returns parent text + an appended block. It performs no substitution,
  deletion, or reordering, so the parent's own text survives verbatim
  inside the child, and the parent row itself is never passed to this
  module at all (only its text).
- **Duplicate approval/version creation is prevented.**
  `compute_approval_fingerprint` is a stable hash over exactly the
  inputs that determine the generated content, so re-submitting the
  same approvals produces the same fingerprint and the service can
  return the existing record instead of creating a second child.

Why the appended block uses the heading it does: the deterministic
resume analyzer's `detect_sections`
(apps/api/services/resume_ai/deterministic.py) only recognizes headings
in its own alias table, and an *unrecognized* heading does not close the
preceding section. Appending under a made-up heading would therefore let
the new content fall inside a trailing "Skills" section, where
`analyze_skill_evidence` counts it as `skills_only` (which the ATS
engine scores `partial`) rather than as demonstrated experience (which
it scores `matched`). `IMPROVEMENT_SECTION_HEADING` is a recognized
`experience` alias, so the block always starts a new section and the
candidate's confirmed statements are evaluated consistently regardless
of how the parent resume happens to be laid out. This is a choice about
where text is placed - it changes no scoring rule and touches no file
under `services/ats_alignment`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass


ENGINE_VERSION = "1.0"

# Must stay an exact alias of the `experience` section in
# apps/api/services/resume_ai/deterministic.py's `SECTION_ALIASES` - see
# the module docstring for why. A test pins this.
IMPROVEMENT_SECTION_HEADING = "Professional Experience"

BULLET_PREFIX = "- "

# Control characters (other than newline/tab) are stripped from user
# content before it is written: a resume version's text is rendered in
# the UI and fed to the deterministic analyzer, and neither has any use
# for them.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ImprovementValidationError(ValueError):
    """Raised when a submitted decision set violates one of the rules
    above. `code` is a stable identifier so the API layer and its tests
    do not have to match on prose."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class GapReference:
    """The subset of a stored `GapAnalysis` gap this module needs.

    Built by the service from the persisted Gap Analysis result and
    passed in verbatim. `suggestion_type` arriving from here (rather
    than from the request) is what makes the `ADD_IF_TRUE` truth check
    unbypassable.
    """

    requirement_id: str
    requirement_text: str
    category: str
    suggestion_type: str


@dataclass(frozen=True)
class ValidatedDecision:
    """One decision that has passed every rule in `validate_decisions`."""

    requirement_id: str
    requirement_text: str
    category: str
    suggestion_type: str
    action: str
    truth_confirmed: bool
    applied_text: str | None

    @property
    def content_source(self) -> str:
        return "user" if self.applied_text else "none"


def sanitize_user_content(value: str | None) -> str:
    """Normalize user-authored content without changing its wording.

    Strips control characters, normalizes line endings, collapses runs
    of blank lines, and trims each line - it never rewrites, expands, or
    reorders what the user wrote.
    """
    if not value:
        return ""

    text = _CONTROL_CHARACTERS.sub("", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [line.strip() for line in text.split("\n")]

    return "\n".join(line for line in lines if line).strip()


def validate_decisions(
    *,
    decisions: list[dict],
    gaps_by_requirement_id: dict[str, GapReference],
) -> list[ValidatedDecision]:
    """Apply every approval rule to a submitted decision set.

    `decisions` entries are the plain dicts of
    `contracts.ImprovementDecisionInput` (`requirement_id`, `action`,
    `truth_confirmed`, `user_content`). `gaps_by_requirement_id` is
    built from the *stored* Gap Analysis row.

    Raises `ImprovementValidationError` on the first violation rather
    than returning a partially-valid set: an approval set that contains
    an unconfirmed `ADD_IF_TRUE` is not "mostly fine", it is a set the
    user has not actually authorized.
    """
    seen: set[str] = set()
    validated: list[ValidatedDecision] = []

    for decision in decisions:
        requirement_id = (decision.get("requirement_id") or "").strip()

        if not requirement_id:
            raise ImprovementValidationError(
                "unknown_requirement",
                "Every decision must reference a requirement.",
            )

        if requirement_id in seen:
            raise ImprovementValidationError(
                "duplicate_decision",
                f"Requirement '{requirement_id}' was decided more than once.",
            )

        seen.add(requirement_id)

        gap = gaps_by_requirement_id.get(requirement_id)

        # A requirement that is not a gap in the stored Gap Analysis is
        # not something the user can approve a change for. This is what
        # stops a client from inventing a requirement to attach content
        # to.
        if gap is None:
            raise ImprovementValidationError(
                "unknown_requirement",
                f"Requirement '{requirement_id}' is not part of this "
                "Gap Analysis result.",
            )

        action = decision.get("action")

        if action not in ("approve", "skip"):
            raise ImprovementValidationError(
                "invalid_action",
                f"Unsupported decision '{action}'.",
            )

        if action == "skip":
            validated.append(
                ValidatedDecision(
                    requirement_id=gap.requirement_id,
                    requirement_text=gap.requirement_text,
                    category=gap.category,
                    suggestion_type=gap.suggestion_type,
                    action="skip",
                    # A skip carries no confirmation, whatever the
                    # request said - there is nothing to confirm.
                    truth_confirmed=False,
                    applied_text=None,
                )
            )
            continue

        content = sanitize_user_content(decision.get("user_content"))

        if not content:
            raise ImprovementValidationError(
                "content_required",
                f'Approving "{gap.requirement_text}" requires your own '
                "wording — NERO never writes resume content for you.",
            )

        truth_confirmed = bool(decision.get("truth_confirmed"))

        # The suggestion type comes from the stored Gap Analysis row, so
        # this check cannot be avoided by the client relabelling a gap.
        if gap.suggestion_type == "ADD_IF_TRUE" and not truth_confirmed:
            raise ImprovementValidationError(
                "truth_confirmation_required",
                f'"{gap.requirement_text}" can only be added if you '
                "confirm it is accurate.",
            )

        validated.append(
            ValidatedDecision(
                requirement_id=gap.requirement_id,
                requirement_text=gap.requirement_text,
                category=gap.category,
                suggestion_type=gap.suggestion_type,
                action="approve",
                truth_confirmed=truth_confirmed,
                applied_text=content,
            )
        )

    if not any(decision.action == "approve" for decision in validated):
        raise ImprovementValidationError(
            "no_approvals",
            "Approve at least one suggestion to create a new resume version.",
        )

    return validated


def build_improved_content(
    *,
    parent_content: str,
    decisions: list[ValidatedDecision],
) -> str:
    """Produce the child version's text: the parent's text, unchanged,
    plus one appended block of approved, user-authored lines.

    The parent's own text is never edited, reordered, or removed - the
    result always starts with it verbatim. The only characters this
    function contributes are `IMPROVEMENT_SECTION_HEADING`, the `- `
    bullet prefixes, and newlines.
    """
    approved = [
        decision
        for decision in decisions
        if decision.action == "approve" and decision.applied_text
    ]

    if not approved:
        return parent_content

    lines = [IMPROVEMENT_SECTION_HEADING]

    for decision in approved:
        for line in decision.applied_text.split("\n"):
            lines.append(f"{BULLET_PREFIX}{line}")

    return f"{parent_content.rstrip()}\n\n" + "\n".join(lines) + "\n"


def compute_approval_fingerprint(
    *,
    gap_analysis_id: str,
    parent_resume_version_id: str,
    decisions: list[ValidatedDecision],
) -> str:
    """A stable SHA-256 over exactly what determines the generated
    version: which Gap Analysis, which parent version, and every
    approved requirement's confirmed, user-authored text.

    Skipped decisions are excluded on purpose. Skipping a suggestion and
    never seeing it are the same thing as far as the produced resume
    goes, so two submissions that approve the same content must collide
    even if the user toggled an unrelated suggestion in between -
    otherwise "prevent duplicate version creation" would be trivially
    defeated. Ordering is normalized so the order the UI submitted
    decisions in cannot produce a second, identical version either.
    """
    payload = {
        "gap_analysis_id": gap_analysis_id,
        "parent_resume_version_id": parent_resume_version_id,
        "approved": sorted(
            (
                {
                    "requirement_id": decision.requirement_id,
                    "suggestion_type": decision.suggestion_type,
                    "truth_confirmed": decision.truth_confirmed,
                    "applied_text": decision.applied_text,
                }
                for decision in decisions
                if decision.action == "approve"
            ),
            key=lambda item: item["requirement_id"],
        ),
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def next_improvement_version_name(existing_names: list[str]) -> str:
    """Name the child version. Kept separate from the upload path's
    `_next_version_name` (which counts all versions of one resume) so an
    improvement version reads as what it is, and so renaming one
    scheme's versions never renumbers the other's."""
    prefix = "Improved"

    used = set()

    for name in existing_names:
        match = re.fullmatch(rf"{prefix} (\d+)", name.strip())
        if match:
            used.add(int(match.group(1)))

    number = 1
    while number in used:
        number += 1

    return f"{prefix} {number}"


# ---------------------------------------------------------------------------
# Comparison (arithmetic over two stored ATS results - no scoring here)
# ---------------------------------------------------------------------------

_STATUS_RANK = {"missing": 0, "partial": 1, "matched": 2}


def _direction(before: str | None, after: str | None) -> str:
    if before is None:
        return "added"

    if after is None:
        return "removed"

    before_rank = _STATUS_RANK.get(before, 0)
    after_rank = _STATUS_RANK.get(after, 0)

    if after_rank > before_rank:
        return "improved"

    if after_rank < before_rank:
        return "regressed"

    return "unchanged"


def build_transitions(
    *,
    baseline_requirements: list[dict],
    recheck_requirements: list[dict],
    approved_requirement_ids: set[str],
) -> list[dict]:
    """Pair each requirement's baseline status with its recheck status.

    Both sides are read from stored `AtsAlignmentResult` rows. A
    requirement present on only one side is reported as `added` or
    `removed` rather than being silently dropped - that happens when the
    JD's Requirement Intelligence snapshot changed between the two runs,
    and hiding it would misrepresent the comparison.
    """
    baseline_by_id = {
        item["requirement_id"]: item for item in baseline_requirements
    }
    recheck_by_id = {
        item["requirement_id"]: item for item in recheck_requirements
    }

    ordered_ids = list(baseline_by_id) + [
        requirement_id
        for requirement_id in recheck_by_id
        if requirement_id not in baseline_by_id
    ]

    transitions: list[dict] = []

    for requirement_id in ordered_ids:
        before = baseline_by_id.get(requirement_id)
        after = recheck_by_id.get(requirement_id)
        reference = after or before

        transitions.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": reference["requirement_text"],
                "category": reference["category"],
                "before_status": before["status"] if before else None,
                "after_status": after["status"] if after else None,
                "direction": _direction(
                    before["status"] if before else None,
                    after["status"] if after else None,
                ),
                "was_approved": requirement_id in approved_requirement_ids,
            }
        )

    return transitions


def build_comparison(
    *,
    baseline_id: str,
    baseline_resume_version_id: str,
    baseline_score: float,
    baseline_result: dict,
    recheck_id: str,
    recheck_resume_version_id: str,
    recheck_score: float,
    recheck_result: dict,
    approved_requirement_ids: set[str],
) -> dict:
    """Assemble the before/after comparison from two stored results.

    Every number here is either copied from one of the two rows or is a
    subtraction of two such numbers. No ATS weight, threshold, or
    formula is read or reproduced - see
    docs/ARCHITECTURE.md's AJI-021 section.
    """
    transitions = build_transitions(
        baseline_requirements=baseline_result.get("requirement_results", []),
        recheck_requirements=recheck_result.get("requirement_results", []),
        approved_requirement_ids=approved_requirement_ids,
    )

    baseline_must_matched = baseline_result.get("must_have_matched", 0)
    recheck_must_matched = recheck_result.get("must_have_matched", 0)
    baseline_preferred_matched = baseline_result.get("preferred_matched", 0)
    recheck_preferred_matched = recheck_result.get("preferred_matched", 0)

    return {
        "baseline_ats_alignment_id": baseline_id,
        "baseline_resume_version_id": baseline_resume_version_id,
        "baseline_score": baseline_score,
        "baseline_must_have_matched": baseline_must_matched,
        "baseline_must_have_total": baseline_result.get("must_have_total", 0),
        "baseline_preferred_matched": baseline_preferred_matched,
        "baseline_preferred_total": baseline_result.get("preferred_total", 0),
        "recheck_ats_alignment_id": recheck_id,
        "recheck_resume_version_id": recheck_resume_version_id,
        "recheck_score": recheck_score,
        "recheck_must_have_matched": recheck_must_matched,
        "recheck_must_have_total": recheck_result.get("must_have_total", 0),
        "recheck_preferred_matched": recheck_preferred_matched,
        "recheck_preferred_total": recheck_result.get("preferred_total", 0),
        "score_delta": round(recheck_score - baseline_score, 2),
        "must_have_delta": recheck_must_matched - baseline_must_matched,
        "preferred_delta": (
            recheck_preferred_matched - baseline_preferred_matched
        ),
        "improved_count": sum(
            1 for item in transitions if item["direction"] == "improved"
        ),
        "unchanged_count": sum(
            1 for item in transitions if item["direction"] == "unchanged"
        ),
        "regressed_count": sum(
            1 for item in transitions if item["direction"] == "regressed"
        ),
        "transitions": transitions,
    }
