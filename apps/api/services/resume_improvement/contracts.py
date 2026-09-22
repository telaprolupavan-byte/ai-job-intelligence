"""The Resume Improvement Approval & Recheck contract (AJI-021).

Where the earlier artifacts sit:

| | Question it answers |
|---|---|
| ATS Alignment (AJI-013) | "How well does this exact resume demonstrate this exact JD?" |
| Gap Analysis (AJI-015) | "Why is each unmet requirement a gap, and what could the candidate truthfully do about it?" |
| **Resume Improvement (this module)** | **"Which of those suggestions did the user explicitly approve, what did applying them produce, and did the score actually move?"** |

Three properties of this contract carry the ticket's safety rules, and
none of them is advisory:

- `ImprovementDecisionInput` deliberately has **no** `suggestion_type`
  field. The suggestion type is always read from the stored
  `GapAnalysis` row for that `requirement_id`, so a client cannot
  relabel an `ADD_IF_TRUE` gap as `REPHRASE_EXISTING` to escape the
  truth-confirmation requirement.
- `ImprovementDecisionRecord.applied_text` is the user's own text,
  verbatim. There is no field anywhere in this contract through which
  the system, an AI provider, or a Gap Analysis suggestion string can
  contribute resume content - see
  `apps.api.services.resume_improvement.engine.build_improved_content`.
- `ImprovementComparison` is derived arithmetically from two stored
  `AtsAlignmentResult` rows. It has no score of its own and no scoring
  parameters; the ATS formula (`services.ats_alignment`) is neither
  re-implemented nor consulted here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Mirrors apps.api.services.gap_analysis.contracts exactly - Resume
# Improvement reads these values from an existing GapAnalysis row, it
# never invents a category, status, or suggestion type of its own.
RequirementCategory = Literal["must_have", "preferred"]
SuggestionType = Literal[
    "ADD_IF_TRUE",
    "REPHRASE_EXISTING",
    "HIGHLIGHT_EXISTING",
]

# Mirrors services.ats_alignment.contracts.AlignmentStatus.
AlignmentStatus = Literal["matched", "partial", "missing"]

DecisionAction = Literal["approve", "skip"]

# "user" is the only value a decision that changed the resume can have.
# "none" is for a skipped decision, which contributes nothing.
ContentSource = Literal["user", "none"]

TransitionDirection = Literal[
    "improved",
    "unchanged",
    "regressed",
    "added",
    "removed",
]

# "pending" only ever describes the window between the child version
# being durably committed and its recheck finishing - it is what a row
# is left at if the process dies mid-recheck, so the version is still
# there and the recheck is still retryable. It is never a state the
# child version's existence depends on.
RecheckStatus = Literal["pending", "complete", "failed"]


# Bounds on user-authored content. Long enough for a real resume bullet
# or two, short enough that a single decision cannot be used to paste an
# arbitrary document into the version.
MAX_USER_CONTENT_LENGTH = 2000
MAX_DECISIONS = 100


class ImprovementDecisionInput(BaseModel):
    """One user decision about one Gap Analysis suggestion, as submitted.

    `extra="forbid"` is deliberate: a request that carries a
    `suggestion_type`, an `applied_text`, or any other field that would
    let the client steer what gets written into the resume is rejected
    outright rather than silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    requirement_id: str = Field(min_length=1, max_length=200)
    action: DecisionAction

    # Only meaningful for an approved ADD_IF_TRUE decision, where it is
    # mandatory. Defaults to False so omitting it can never be read as
    # confirmation.
    truth_confirmed: bool = False

    # The candidate's own wording. Required for every approved decision
    # (see engine.validate_decisions); ignored entirely for a skip.
    user_content: str | None = Field(
        default=None,
        max_length=MAX_USER_CONTENT_LENGTH,
    )


class ResumeImprovementRequest(BaseModel):
    """The POST body: which Gap Analysis is being acted on, and the
    user's decision for each of its gaps."""

    model_config = ConfigDict(extra="forbid")

    gap_analysis_id: str = Field(min_length=1)
    decisions: list[ImprovementDecisionInput] = Field(
        min_length=1,
        max_length=MAX_DECISIONS,
    )


class ImprovementDecisionRecord(BaseModel):
    """The persisted record of one decision.

    `requirement_text`, `category`, and `suggestion_type` are copied
    verbatim from the stored `GapAnalysis` gap - never from the request.
    `applied_text` is the user's own text, verbatim, and is `None` for a
    skipped decision.
    """

    requirement_id: str
    requirement_text: str
    category: RequirementCategory
    suggestion_type: SuggestionType

    action: DecisionAction
    truth_confirmed: bool

    applied_text: str | None
    content_source: ContentSource


class RequirementTransition(BaseModel):
    """How one requirement's ATS Alignment status changed between the
    baseline result and the recheck. Both statuses are read from stored
    results; nothing is re-scored to produce this."""

    requirement_id: str
    requirement_text: str
    category: RequirementCategory

    before_status: AlignmentStatus | None
    after_status: AlignmentStatus | None
    direction: TransitionDirection

    # True when this exact requirement was one the user approved a
    # suggestion for, so the UI can distinguish a movement the user
    # acted on from an incidental one.
    was_approved: bool = False


class ImprovementComparison(BaseModel):
    """The before/after view, derived entirely from two stored
    `AtsAlignmentResult` rows.

    A negative `score_delta` is a legitimate, faithfully-reported
    outcome, not an error: the recheck runs the same unmodified ATS
    engine over a longer resume, and the honest answer is whatever it
    returns.
    """

    baseline_ats_alignment_id: str
    baseline_resume_version_id: str
    baseline_score: float
    baseline_must_have_matched: int
    baseline_must_have_total: int
    baseline_preferred_matched: int
    baseline_preferred_total: int

    recheck_ats_alignment_id: str
    recheck_resume_version_id: str
    recheck_score: float
    recheck_must_have_matched: int
    recheck_must_have_total: int
    recheck_preferred_matched: int
    recheck_preferred_total: int

    score_delta: float
    must_have_delta: int
    preferred_delta: int

    improved_count: int = 0
    unchanged_count: int = 0
    regressed_count: int = 0

    transitions: list[RequirementTransition] = Field(default_factory=list)


class ResumeImprovementResult(BaseModel):
    """The full stored result for one approval + version creation +
    recheck cycle.

    `comparison` is `None` whenever the recheck has not produced a
    result yet - a failed recheck still leaves a complete, valid record
    of the approved decisions and the child version that was created
    and kept.
    """

    engine_version: str

    job_id: str
    gap_analysis_id: str

    parent_resume_version_id: str
    child_resume_version_id: str
    child_resume_version_name: str

    approved_count: int = 0
    skipped_count: int = 0

    decisions: list[ImprovementDecisionRecord] = Field(default_factory=list)

    comparison: ImprovementComparison | None = None
