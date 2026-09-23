"""Deterministic Job Priority Ranking (AJI-025).

Orders the jobs a user has already analyzed for their attention, from
existing Hard Eligibility, Job Match and ATS Alignment results. Pure: no
database access, no AI call. See engine.py for the ordering rule and
docs/ARCHITECTURE.md for the full rationale.
"""

from services.priority_ranking.contracts import (
    AtsAlignmentEvidence,
    BlockingFactor,
    JobMatchEvidence,
    PriorityCandidate,
    PriorityReason,
    PriorityResult,
    PriorityState,
)
from services.priority_ranking.engine import ENGINE_VERSION, ORDERING, rank_jobs

__all__ = [
    "AtsAlignmentEvidence",
    "BlockingFactor",
    "ENGINE_VERSION",
    "JobMatchEvidence",
    "ORDERING",
    "PriorityCandidate",
    "PriorityReason",
    "PriorityResult",
    "PriorityState",
    "rank_jobs",
]
