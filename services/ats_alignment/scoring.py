"""ATS Alignment overall-score/confidence aggregation (AJI-013 section 10).

IMPORTANT — placeholder formula, not a product decision:

The AJI-013 spec explicitly states that no Must-Have/Preferred/
Nice-to-Have scoring-weight formula has been approved by the Project
Owner, and instructs the Builder not to invent one (no 80/20, 70/20/10,
or similar unapproved weighting). Per that instruction, this module
implements the simplest defensible placeholder — every requirement
counts equally regardless of category — isolated behind two small,
independently-testable functions so the real, approved formula can
replace `compute_overall_score`'s body later without touching the
engine, the persistence layer, or the API. `SCORING_VERSION` is recorded
on every persisted `AtsAlignmentResult` row precisely so a future formula
change is auditable/detectable like any other analyzer version bump, the
same way `JobMatchResult.engine_version` already works.

Do not read `SCORING_VERSION` or this module's behavior as an approved
weighting policy.
"""

from __future__ import annotations

from collections import Counter

from services.ats_alignment.contracts import Confidence, RequirementAlignment


SCORING_VERSION = "placeholder-1.0"


_STATUS_POINTS: dict[str, float] = {
    "matched": 1.0,
    "partial": 0.5,
    "missing": 0.0,
}


def compute_overall_score(
    requirement_results: list[RequirementAlignment],
) -> float | None:
    """
    Every requirement (must-have or preferred) is weighted equally.

    Returns None when there is nothing to score — the caller must never
    persist a fabricated score for a Job Intelligence snapshot with no
    analyzable requirements (AJI-013 section 19, "no score when required
    inputs are invalid").
    """
    if not requirement_results:
        return None

    total_points = sum(
        _STATUS_POINTS[result.status] for result in requirement_results
    )

    return round(100 * total_points / len(requirement_results), 2)


def compute_overall_confidence(
    requirement_results: list[RequirementAlignment],
) -> Confidence | None:
    """
    Deterministic aggregation of per-requirement analysis confidence.

    This reflects confidence in the ATS engine's own evidence
    interpretation (per-requirement), never an employability/hiring
    prediction (AJI-013 section 11).
    """
    if not requirement_results:
        return None

    counts = Counter(result.confidence for result in requirement_results)
    total = len(requirement_results)

    if counts["low"] / total > 0.3:
        return "low"

    if counts["high"] == total:
        return "high"

    return "medium"
