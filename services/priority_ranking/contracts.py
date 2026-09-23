"""Job Priority Ranking (AJI-025) pure, DB-free, AI-free contracts.

Mirrors services.eligibility's / services.job_matching's convention: this
package has no dependency on apps.api (no DB, no FastAPI, no AI provider).
The orchestration layer (apps/api/services/priority_ranking_service.py)
turns persisted rows into the plain dataclasses below before calling
services.priority_ranking.engine.

Priority Ranking answers only: "given the analyses NERO already has for
this user, in what order do these jobs deserve the user's attention?" It
never predicts interviews, offers, or hiring, and it never produces a
score of its own - see engine.py for why the result is an ordering, not a
number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from services.eligibility.contracts import EligibilityResult


class PriorityState(str, Enum):
    """Where a job stands in priority ranking.

    - RANKED: not ruled out by Hard Eligibility, and ordered from a
      current Job Match and a current ATS Alignment for the selected
      resume version.
    - PARTIAL: ordered from a Job Match, but the ATS Alignment is missing
      or one of the analyses is out of date (see its cautions).
    - NOT_READY: not ruled out, but there is no Job Match for the
      selected resume version, so there is nothing to order it by yet.
      It is listed, never given a rank, never treated as low priority.
    - EXCLUDED: Hard Eligibility is INELIGIBLE. Never ranked, whatever
      its Job Match or ATS Alignment says.
    """

    RANKED = "ranked"
    PARTIAL = "partial"
    NOT_READY = "not_ready"
    EXCLUDED = "excluded"


ReasonSource = Literal["eligibility", "job_match", "ats_alignment"]

# "evidence": a fact the ordering used. "caution": a limitation of that
# evidence (unknown eligibility, a missing or out-of-date analysis).
ReasonKind = Literal["evidence", "caution"]


@dataclass(frozen=True)
class PriorityReason:
    code: str
    source: ReasonSource
    kind: ReasonKind
    message: str


@dataclass(frozen=True)
class BlockingFactor:
    """Why a job has no rank: a failed hard constraint, or no Job Match."""

    code: str
    source: ReasonSource
    message: str


@dataclass(frozen=True)
class JobMatchEvidence:
    """The latest persisted Job Match for (user, job, resume version)."""

    id: str
    score: float
    engine_version: str
    # NULL on rows persisted before AJI-014 (no Job Intelligence behind them).
    job_intelligence_id: str | None
    must_have_matched: int
    must_have_total: int


@dataclass(frozen=True)
class AtsAlignmentEvidence:
    """The latest persisted ATS Alignment for (user, job, resume version)."""

    id: str
    overall_score: float
    engine_version: str
    job_intelligence_id: str
    # NULL on rows persisted before AJI-020C.
    requirement_intelligence_id: str | None
    must_have_matched: int
    must_have_total: int


@dataclass(frozen=True)
class PriorityCandidate:
    """Everything the engine needs about one job, already loaded.

    ``latest_job_intelligence_id`` / ``latest_requirement_intelligence_id``
    are the snapshots a recalculation would use right now (the same
    "latest" lookups calculate_job_match/calculate_ats_alignment make), so
    the engine can tell whether a stored analysis is still current.
    """

    job_id: str
    posting_date: datetime | None
    eligibility: EligibilityResult
    job_match: JobMatchEvidence | None = None
    ats_alignment: AtsAlignmentEvidence | None = None
    latest_job_intelligence_id: str | None = None
    latest_requirement_intelligence_id: str | None = None


@dataclass(frozen=True)
class PriorityResult:
    job_id: str
    state: PriorityState
    # 1-based position among RANKED/PARTIAL jobs; None for NOT_READY and
    # EXCLUDED, which are listed but never ranked.
    rank: int | None
    eligibility_status: str
    reasons: list[PriorityReason] = field(default_factory=list)
    blocking_factors: list[BlockingFactor] = field(default_factory=list)
    job_match_current: bool | None = None
    ats_alignment_current: bool | None = None
