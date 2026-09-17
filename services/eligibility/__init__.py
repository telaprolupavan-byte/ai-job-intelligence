"""Deterministic Hard Eligibility Engine.

Runs before Job Match / ATS Alignment / priority ranking to decide
whether a job is even a candidate for the user at all — see
docs/ARCHITECTURE.md ("Hard Eligibility vs. Job Match vs. ATS Alignment")
for the full pipeline ordering and the hard-constraint-vs-soft-preference
rationale.

This package has no dependency on apps.api or the database, and makes no
AI/LLM calls, so it can be unit tested in isolation and reused from any
future orchestration layer (Job Intelligence, ATS Alignment, etc.).
"""

from services.eligibility.contracts import (
    ConstraintStatus,
    EligibilityCheck,
    EligibilityResult,
    EligibilityStatus,
    JobEligibilitySignals,
    UserEligibilityCriteria,
    WorkAuthorizationSignals,
)
from services.eligibility.engine import evaluate_eligibility
from services.eligibility.job_signals import extract_work_authorization_signals

__all__ = [
    "ConstraintStatus",
    "EligibilityCheck",
    "EligibilityResult",
    "EligibilityStatus",
    "JobEligibilitySignals",
    "UserEligibilityCriteria",
    "WorkAuthorizationSignals",
    "evaluate_eligibility",
    "extract_work_authorization_signals",
]
