"""The General Resume Intelligence contract (AJI-027).

Where this sits relative to the job-specific pipeline:

| | Question it answers |
|---|---|
| ATS Alignment / Job Match / Gap Analysis | "How does this resume read against *this job*?" |
| **General Resume Intelligence (this package)** | **"How well is this resume written, on its own terms, and what could the user improve?"** |

The General Resume Score is computed from the resume's own text only. No
field in this contract refers to a job, a requirement, or an ATS result,
and nothing here is an estimate of how any employer's ATS would read the
resume.

Three properties carry the ticket's safety rules:

- `ReviewDecisionInput` has **no** `suggestion_type` and no field for
  system-authored text. The suggestion type is read from the stored
  assessment, and the only resume text that can be written is the user's
  own `user_content`.
- `Improvement.explanation`/`guidance` are the only fields the AI may
  author, and `*_source` records whether each came from the AI or from a
  deterministic template.
- `ScoreComponent`/`GeneralResumeAssessmentResult` have no band, label or
  threshold field. A score is a number and a breakdown, nothing more.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.api.services.resume_improvement.contracts import (
    MAX_DECISIONS,
    MAX_USER_CONTENT_LENGTH,
)


ComponentKey = Literal[
    "structure",
    "action_writing",
    "measurable_impact",
    "clarity",
    "skill_evidence",
]

# "insufficient_data": there was nothing to measure (e.g. no bullets), so
# the component is excluded from the average and surfaced as an
# improvement area instead of being scored as zero.
ComponentStatus = Literal["scored", "insufficient_data"]

ImprovementKind = Literal[
    "bullet",
    "missing_section",
    "missing_contact",
    "skill_not_demonstrated",
    "no_bullets",
    "inconsistent_headings",
    "no_impact_bullets",
    "no_recognized_skills",
]

# REPHRASE_EXISTING: rewording an existing line.
# ADD_IF_TRUE: adds a new factual claim (a number, a section, a skill in
#   context, a contact detail) - approval requires truth confirmation.
# ADVISORY: cannot be applied as a text change; the user can only reject
#   (dismiss) it, or fix it by uploading a new version.
SuggestionType = Literal["REPHRASE_EXISTING", "ADD_IF_TRUE", "ADVISORY"]

BulletIssue = Literal["weak_phrase", "no_action_verb", "no_quantification"]

TextSource = Literal["ai", "deterministic"]

GenerationStatus = Literal["complete", "partial"]

DecisionAction = Literal["approve", "reject"]

RecheckStatus = Literal["not_required", "pending", "complete", "failed"]

ReadinessState = Literal[
    "not_assessed",
    "not_valid",
    "needs_review",
    "recheck_pending",
    "recheck_failed",
    "superseded",
    "ready",
]

ImprovementTransition = Literal["resolved", "still_present", "new"]


class ScoreComponent(BaseModel):
    key: ComponentKey
    label: str
    status: ComponentStatus
    # 0-100 when scored, None when insufficient_data.
    score: float | None
    # The share this component contributed to the overall average. Equal
    # across scored components; 0 for an insufficient_data component.
    weight: float
    numerator: int
    denominator: int
    detail: str


class Improvement(BaseModel):
    improvement_id: str
    kind: ImprovementKind
    suggestion_type: SuggestionType
    components: list[ComponentKey] = Field(default_factory=list)
    issues: list[BulletIssue] = Field(default_factory=list)

    # A short, deterministic statement of what was detected.
    title: str

    # Verbatim resume text this improvement is anchored to (a bullet line
    # without its marker), or None when the issue is an absence (a
    # missing section, a missing contact detail).
    evidence: str | None = None

    # The exact, stripped line (with its marker) a bullet improvement
    # replaces. Internal to the apply step; never user-authored.
    anchor_line: str | None = None

    # What the improvement targets: a section name, "email"/"phone", or a
    # canonical skill. None for bullets.
    target: str | None = None

    explanation: str
    explanation_source: TextSource = "deterministic"
    guidance: str
    guidance_source: TextSource = "deterministic"


class ValidationSummary(BaseModel):
    valid: bool
    warnings: list[str] = Field(default_factory=list)
    word_count: int = 0
    section_matches: list[str] = Field(default_factory=list)


class GeneralResumeAssessmentResult(BaseModel):
    analysis_version: str
    analyzer_version: str
    scoring_version: str
    prompt_version: str

    resume_version_id: str
    overall_score: float
    components: list[ScoreComponent]
    improvements: list[Improvement] = Field(default_factory=list)
    validation: ValidationSummary
    generation_status: GenerationStatus


class ReviewDecisionInput(BaseModel):
    """One user decision about one improvement, as submitted.

    `extra="forbid"`: a request carrying a `suggestion_type`, an
    `applied_text`, or any other field that would let the client steer
    what gets written is rejected outright rather than ignored.
    """

    model_config = ConfigDict(extra="forbid")

    improvement_id: str = Field(min_length=1, max_length=200)
    action: DecisionAction
    truth_confirmed: bool = False
    user_content: str | None = Field(
        default=None,
        max_length=MAX_USER_CONTENT_LENGTH,
    )


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[ReviewDecisionInput] = Field(
        min_length=1,
        max_length=MAX_DECISIONS,
    )


class AssessmentRequest(BaseModel):
    """The POST body for an assessment: intentionally empty. There is no
    job, requirement or preference input to a General Resume Score, and
    `extra="forbid"` makes a client that tries to send one get a 422."""

    model_config = ConfigDict(extra="forbid")


class ReviewDecisionRecord(BaseModel):
    """The persisted record of one decision. `kind`, `suggestion_type`
    and `title` are copied from the stored assessment, never from the
    request; `applied_text` is the user's own text verbatim (None for a
    rejection)."""

    improvement_id: str
    kind: ImprovementKind
    suggestion_type: SuggestionType
    title: str
    action: DecisionAction
    truth_confirmed: bool
    applied_text: str | None


class ComponentDelta(BaseModel):
    key: ComponentKey
    label: str
    before: float | None
    after: float | None
    delta: float | None


class ImprovementChange(BaseModel):
    improvement_id: str
    title: str
    transition: ImprovementTransition
    was_approved: bool = False
    was_rejected: bool = False


class AssessmentComparison(BaseModel):
    """Before/after, derived arithmetically from two stored assessment
    rows. A negative `score_delta` is reported as-is."""

    baseline_assessment_id: str
    baseline_resume_version_id: str
    baseline_score: float
    recheck_assessment_id: str
    recheck_resume_version_id: str
    recheck_score: float
    score_delta: float
    components: list[ComponentDelta] = Field(default_factory=list)
    resolved_count: int = 0
    still_present_count: int = 0
    new_count: int = 0
    changes: list[ImprovementChange] = Field(default_factory=list)
