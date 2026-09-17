from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class ConstraintStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class EligibilityCheck:
    constraint: str
    status: ConstraintStatus
    reason: str


@dataclass
class EligibilityResult:
    status: EligibilityStatus

    checks: list[EligibilityCheck] = field(default_factory=list)

    failed_constraints: list[str] = field(default_factory=list)
    unknown_constraints: list[str] = field(default_factory=list)

    reasons: list[str] = field(default_factory=list)

    engine_version: str = "1.0.0"


@dataclass
class UserEligibilityCriteria:
    """
    Pure, DB-free representation of a user's HARD eligibility constraints.

    This is deliberately narrower than the Preference/Profile models: only
    fields that represent an explicit hard restriction belong here. A
    preference that should remain a *soft* Job Match signal (e.g. salary
    minimums, target titles) is never modeled in this shape. See
    apps/api/services/eligibility_service.py for how this is built from
    the Preference/Profile ORM models, and docs/ARCHITECTURE.md for the
    hard-vs-soft rationale.
    """

    allowed_employment_types: list[str] | None = None

    included_locations: list[str] | None = None
    excluded_locations: list[str] | None = None

    required_remote_type: str | None = None

    requires_sponsorship: bool | None = None
    is_us_citizen: bool | None = None
    has_security_clearance: bool | None = None

    enforce_minimum_experience: bool = False
    user_years_experience: float | None = None


@dataclass
class WorkAuthorizationSignals:
    """
    Deterministic, keyword-based signals extracted from job text.

    ``sponsorship_available`` is a tri-state: True/False when the JD makes
    an explicit statement either way, None when it says nothing decisive.

    ``authorization_required``/``citizenship_required``/``clearance_required``
    are booleans that are True only when explicit language was found.
    False means "not mentioned" — job postings essentially never state a
    requirement's explicit *absence*, so False must never be read as "this
    requirement definitely does not apply".
    """

    sponsorship_available: bool | None = None
    authorization_required: bool = False
    citizenship_required: bool = False
    clearance_required: bool = False


@dataclass
class JobEligibilitySignals:
    """
    Pure, DB-free representation of a job's observable eligibility
    signals. Built once per job from already-loaded Job data (see
    apps/api/services/eligibility_service.py) — this package itself never
    touches the database.
    """

    employment_type: str | None = None
    location: str | None = None
    remote_type: str | None = None

    work_authorization: WorkAuthorizationSignals = field(
        default_factory=WorkAuthorizationSignals
    )

    minimum_years_required: float | None = None
