"""Centralized, configurable ATS Alignment scoring weights (AJI-020).

AJI-013 shipped `compute_overall_score()` as an explicitly-documented
placeholder (every requirement counts equally, `SCORING_VERSION =
"placeholder-1.0"`) because no Must-Have/Preferred weighting formula had
been approved at the time (see docs/ARCHITECTURE.md's "Scoring: an
explicit placeholder formula"). AJI-020 delivers the approved real
formula: a deterministic composite of four independently-scored
dimensions, each a fixed percentage of the overall 0-100 score.

These weights are the single source of truth for the formula. They are
intentionally isolated in their own module (not inlined in scoring.py)
so a future, still-unapproved change (e.g. re-weighting per job family)
touches exactly one place, mirroring how
`services/job_matching/scorer.py` keeps its own component `max_score`
values as the one place Job Match's weighting lives.

Do not read a component's weight as independent of the others — they are
defined together and must always sum to 1.0 (enforced by
`test_ats_scoring_weights.py`), since `compute_overall_score()` produces
a single 0-100 score by summing `weight * component_score` across all
four.
"""

from __future__ import annotations

# Fraction of the overall 0-100 ATS Alignment score contributed by each
# dimension. Approved baseline weights (AJI-020 Planner specification):
REQUIREMENT_COVERAGE_WEIGHT = 0.40
KEYWORD_ALIGNMENT_WEIGHT = 0.25
RESUME_EVIDENCE_WEIGHT = 0.25
STRUCTURE_PARSEABILITY_WEIGHT = 0.10

SCORE_WEIGHTS: dict[str, float] = {
    "requirement_coverage": REQUIREMENT_COVERAGE_WEIGHT,
    "keyword_terminology_alignment": KEYWORD_ALIGNMENT_WEIGHT,
    "resume_evidence_experience": RESUME_EVIDENCE_WEIGHT,
    "structure_parseability": STRUCTURE_PARSEABILITY_WEIGHT,
}

# Bump whenever a weight value (or the set of components) changes, so a
# persisted AtsAlignmentResult's `scoring_version` always identifies
# exactly which formula produced it. Independent of `engine.ENGINE_VERSION`
# (which also changes on non-weighting scoring logic changes) but the two
# are bumped together in practice since this module has no callers other
# than the engine.
SCORING_VERSION = "weighted-1.0"
