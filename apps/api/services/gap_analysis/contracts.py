"""The Gap Analysis & Job-Specific Suggestions contract (AJI-015).

Gap Analysis answers a narrower question than every artifact before it:

| | Question it answers |
|---|---|
| Job Intelligence | "What does this job require?" |
| ATS Alignment | "How well does this exact resume demonstrate this exact JD?" |
| **Gap Analysis (this module)** | **"For each requirement this resume does not fully demonstrate, why is it a gap, and what could the candidate truthfully do about it?"** |
| Job Match | "How well does this job fit?" |

Gap Analysis never re-derives *which* requirements are gaps — that
classification (`matched` / `partial` / `missing`) is read verbatim from
an existing AJI-013 `AtsAlignmentResult`, the canonical requirement-
alignment source. This module only adds a semantic explanation and a
job-specific, evidence-constrained suggestion on top of each non-matched
requirement.

Confidence reuses the existing high/medium/low convention (see
`apps.api.services.job_intelligence.contracts`) rather than introducing a
new numeric-confidence representation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]

# Mirrors services.ats_alignment.contracts exactly — Gap Analysis reads
# these values from an existing AtsAlignmentResult, it never invents a
# third tier or reclassifies a requirement.
GapStatus = Literal["partial", "missing"]
RequirementCategory = Literal["must_have", "preferred"]
RequirementType = Literal["skill", "experience", "education", "certification"]

# The evidence-safety-critical field. `ADD_IF_TRUE` is the only type ever
# used for a `missing` requirement (zero resume evidence exists) — it is
# a conditional prompt for the candidate to confirm before adding
# anything, never an assertion that the candidate already has the
# experience. `REPHRASE_EXISTING` / `HIGHLIGHT_EXISTING` are only ever
# used for a `partial` requirement, where the underlying ATS Alignment
# result already recorded real resume evidence to rephrase/highlight.
SuggestionType = Literal[
    "ADD_IF_TRUE",
    "REPHRASE_EXISTING",
    "HIGHLIGHT_EXISTING",
]

TextSource = Literal["ai", "deterministic"]


class GapSuggestion(BaseModel):
    """One Gap Analysis entry: the AJI-013 requirement result it was
    derived from (copied verbatim, never re-scored), plus a semantic
    explanation and a job-specific suggestion.

    `explanation_source` / `suggestion_source` record whether the AI
    successfully produced a validated value for that field ("ai") or
    whether it fell back to the deterministic template ("deterministic")
    because the AI was unavailable or its output failed the evidence
    check — this is never hidden from the persisted result.
    """

    requirement_id: str = Field(min_length=1)
    requirement_type: RequirementType
    category: RequirementCategory
    requirement_text: str = Field(min_length=1)
    status: GapStatus

    jd_evidence: str = Field(min_length=1)
    resume_evidence: str | None = None

    suggestion_type: SuggestionType

    explanation: str = Field(min_length=1)
    explanation_source: TextSource

    suggestion_text: str = Field(min_length=1)
    suggestion_source: TextSource

    confidence: Confidence


class GapAnalysisResult(BaseModel):
    """The full Gap Analysis result for one (ResumeVersion, Job
    Intelligence snapshot, ATS Alignment result) combination.

    Contains only non-matched requirements — a fully-matched requirement
    has no gap and is not represented here. An empty `gaps` list is a
    valid, meaningful result (the resume has no gaps against this JD),
    not an error.
    """

    analysis_version: str
    job_id: str
    resume_version_id: str
    ats_alignment_id: str

    must_have_gap_count: int = 0
    preferred_gap_count: int = 0

    gaps: list[GapSuggestion] = Field(default_factory=list)
