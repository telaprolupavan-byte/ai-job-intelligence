"""ATS Alignment (AJI-013) pure, DB-free contracts.

This module has no dependency on apps.api (no DB, no FastAPI, no AI
provider) — mirroring services.job_matching's and services.eligibility's
own DB/AI-free-core convention. The apps.api orchestration layer
(apps/api/services/ats_alignment_service.py) is responsible for turning
ORM rows (Job, RequirementIntelligence, ResumeVersion, Profile) into the
plain dataclasses defined here before calling services.ats_alignment.engine.

Category taxonomy note: the AJI-013 spec describes three tiers
(Must-Have / Preferred / Nice-to-Have). AJI-012's `JobIntelligence`
contract only distinguished two levels — `required` and `preferred` —
and ATS Alignment reused that same two-tier taxonomy exactly rather than
forking a third tier. AJI-020C (ATS Alignment / Requirement Intelligence
integration) preserves this unchanged: AJI-020A's `RequirementItem` has
a four-tier `importance` (required/preferred/contextual/informational),
but only `required`/`preferred` items are ever mapped into a
`JobRequirementItem` at all — `contextual`/`informational` items are not
requirements to score a candidate against by AJI-020A's own locked
definition, so they are excluded before reaching this module rather than
forced into a category that doesn't apply to them (see
apps/api/services/ats_alignment_service.py's
`_build_job_requirements_from_requirement_intelligence`).
`RequirementCategory` therefore still has only two values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AlignmentStatus = Literal["matched", "partial", "missing"]
RequirementCategory = Literal["must_have", "preferred"]
RequirementType = Literal["skill", "experience", "education", "certification"]
Confidence = Literal["high", "medium", "low"]

# Mirrors apps.api.services.requirement_intelligence.contracts.
# RelationshipType/ScreeningConstraintStatus exactly (AJI-020A, locked) —
# duplicated here rather than imported so services.ats_alignment keeps
# its existing zero-dependency-on-apps.api property; these are plain
# passthrough value sets, not a second definition of the semantics.
RelationshipType = Literal["AND", "OR", "MIN_COUNT", "EQUIVALENT"]
ScreeningConstraintStatus = Literal[
    "required", "preferred", "disqualifying", "unknown"
]


@dataclass
class JobRequirementItem:
    """One atomic, independently-evaluable requirement, adapted from an
    AJI-020A/B `RequirementIntelligenceResult` snapshot (AJI-020C) by
    `apps.api.services.ats_alignment_service.
    _build_job_requirements_from_requirement_intelligence`.

    `requirement_id` is a stable key (used as the JSON key/anchor in the
    persisted result) — as of AJI-020C it is the originating AJI-020A
    `RequirementItem.id` verbatim (previously a synthetic
    `f"skill:{...}"`-style key derived from AJI-012 data), so a result
    can be traced back to the exact Requirement Intelligence item it
    came from.

    `hard_requirement`/`ambiguous`/`ambiguity_reason` are AJI-020A
    metadata carried through unchanged (AJI-020C section 5/7): they are
    never used to compute `overall_score` or any category total — no
    scoring/weighting/gating rule for them has been approved, and
    AJI-020C does not invent one (see
    docs/ARCHITECTURE.md's AJI-020C "Importance / hard_requirement"
    note). In particular, `importance="required"` never implies
    `hard_requirement=True`, and the reverse is enforced upstream by
    AJI-020A's own locked contract validator.
    """

    requirement_id: str
    requirement_type: RequirementType
    category: RequirementCategory
    requirement_text: str
    jd_evidence: str

    canonical_skill: str | None = None
    minimum_years: float | None = None
    area: str | None = None
    degree_level: str | None = None
    field_of_study: str | None = None
    certification_name: str | None = None

    hard_requirement: bool = False
    ambiguous: bool = False
    ambiguity_reason: str | None = None


@dataclass
class RequirementAlignment:
    """The ATS Alignment result for exactly one JobRequirementItem.

    `hard_requirement`/`ambiguous`/`ambiguity_reason` are passed through
    unchanged from the originating `JobRequirementItem` (see its
    docstring) — never read by `services.ats_alignment.scoring`.
    """

    requirement_id: str
    requirement_type: RequirementType
    category: RequirementCategory
    requirement_text: str
    status: AlignmentStatus
    jd_evidence: str
    resume_evidence: str | None
    explanation: str
    confidence: Confidence

    hard_requirement: bool = False
    ambiguous: bool = False
    ambiguity_reason: str | None = None


@dataclass
class RequirementRelationshipGroup:
    """A descriptive-only pass-through of one AJI-020A `RequirementGroup`
    (AND/OR/MIN_COUNT/EQUIVALENT) (AJI-020C section 6).

    This is surfaced for visibility only and never folded into
    `overall_score`/`must_have_total`/`preferred_total`/etc: the existing
    v1 ATS result contract has no representation for group-level
    fulfillment (there is no concept of "this OR-group counts as one
    satisfied requirement" anywhere in `services.ats_alignment.scoring`),
    and AJI-020C does not invent one — this is a reported architecture
    gap, not an oversight (see docs/ARCHITECTURE.md's AJI-020C
    "Relationship handling" section). `member_requirement_ids` reference
    `JobRequirementItem.requirement_id`/`RequirementAlignment.
    requirement_id` values — but only when the referenced AJI-020A item
    was itself `required`/`preferred` (and therefore present in
    `requirement_results`); a member drawn from a `contextual`/
    `informational` item (never scored — see `JobRequirementItem`'s
    docstring) is passed through verbatim from AJI-020A and may not
    appear in `requirement_results`. This mirrors AJI-020A's own locked
    relationship semantics exactly: flat, non-nested, order-independent,
    referencing `RequirementItem` ids only.
    """

    group_id: str
    relationship: RelationshipType
    member_requirement_ids: list[str]
    minimum_count: int | None
    description: str


@dataclass
class ScreeningConstraintInfo:
    """A descriptive-only pass-through of one AJI-020A `ScreeningConstraint`
    (AJI-020C section 8).

    Never scored as a technical requirement and never mixed into
    `requirement_results`/`overall_score` — screening constraints remain
    separate intelligence, exactly as AJI-020A's own locked contract
    already keeps them separate from `RequirementItem`.
    """

    constraint_id: str
    constraint_type: str
    status: ScreeningConstraintStatus
    statement: str
    raw_text: str


@dataclass
class ScoreComponent:
    """One independently-computed, independently-explainable contributor
    to the overall ATS Alignment score (AJI-020).

    `weight` is this component's fraction of the overall 0-100 score
    (from `services.ats_alignment.weights.SCORE_WEIGHTS`), `score` is its
    own 0-100 value, and `weighted_score` (`weight * score`) is exactly
    what it contributes to `AtsAlignmentResult.overall_score` before the
    required-requirement guardrail is applied. Mirrors
    `services.job_matching.contracts.MatchComponent`'s existing
    explainable-breakdown convention.
    """

    name: str
    weight: float
    score: float
    explanation: str

    @property
    def weighted_score(self) -> float:
        return round(self.weight * self.score, 2)


@dataclass
class AtsAlignmentResult:
    """The full ATS Alignment result for one (resume version, JD) pair."""

    overall_score: float
    confidence: Confidence
    requirement_results: list[RequirementAlignment] = field(default_factory=list)

    must_have_total: int = 0
    must_have_matched: int = 0
    preferred_total: int = 0
    preferred_matched: int = 0

    components: list[ScoreComponent] = field(default_factory=list)
    must_have_ceiling: float | None = None

    engine_version: str = "1.0.0"
    scoring_version: str = "placeholder-1.0"

    # AJI-020C additions — both descriptive-only, never scored (see
    # `RequirementRelationshipGroup`/`ScreeningConstraintInfo` above).
    relationships: list[RequirementRelationshipGroup] = field(default_factory=list)
    screening_constraints: list[ScreeningConstraintInfo] = field(
        default_factory=list
    )
