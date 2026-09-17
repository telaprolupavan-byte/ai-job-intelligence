"""
Deterministic Hard Eligibility Engine.

This module contains no database access and makes no AI/LLM calls. It is
a pure function of (UserEligibilityCriteria, JobEligibilitySignals) ->
EligibilityResult, which is what makes it cheap to run over hundreds or
thousands of jobs and trivial to unit test.

Hard eligibility vs. soft preferences (see docs/ARCHITECTURE.md for the
full rationale): this engine only evaluates constraints the user has
explicitly made restrictive (a non-empty allow-list, an explicit
exclusion, an explicit remote-only requirement, a declared work-
authorization need, or an opted-in experience minimum). A constraint that
is unset is NOT_APPLICABLE and never excludes a job — "do not
automatically convert every preference into a hard constraint". Soft
signals (salary, target titles, ranked preference ordering) are not
modeled here at all; they remain Job Match's concern.

Unknown job data is never silently treated as a match or a mismatch: a
restrictive constraint whose corresponding job signal is missing/unclear
always resolves to ConstraintStatus.UNKNOWN, which surfaces as an overall
EligibilityStatus.UNKNOWN (unless another constraint has already FAILed —
a hard failure always wins, since a high-confidence pass elsewhere must
never mask an explicit disqualification).
"""

from __future__ import annotations

from services.eligibility.contracts import (
    ConstraintStatus,
    EligibilityCheck,
    EligibilityResult,
    EligibilityStatus,
    JobEligibilitySignals,
    UserEligibilityCriteria,
)
from services.eligibility.location import location_token_matches


ENGINE_VERSION = "1.0.0"


def evaluate_eligibility(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityResult:
    """
    Evaluate a job against a user's hard eligibility constraints.

    A FAIL on any single constraint makes the job INELIGIBLE regardless
    of how many other constraints PASS — a strong signal elsewhere (e.g.
    a future high ATS/Job Match score) must never override a hard
    disqualification. Absent a FAIL, any UNKNOWN constraint makes the
    overall result UNKNOWN rather than a confident ELIGIBLE.
    """
    checks = [
        _check_employment_type(criteria, job),
        _check_remote_arrangement(criteria, job),
        _check_location(criteria, job),
        _check_sponsorship(criteria, job),
        _check_citizenship(criteria, job),
        _check_security_clearance(criteria, job),
        _check_experience(criteria, job),
    ]

    failed_constraints = [
        check.constraint
        for check in checks
        if check.status == ConstraintStatus.FAIL
    ]

    unknown_constraints = [
        check.constraint
        for check in checks
        if check.status == ConstraintStatus.UNKNOWN
    ]

    reasons = [
        check.reason
        for check in checks
        if check.status in (ConstraintStatus.FAIL, ConstraintStatus.UNKNOWN)
    ]

    if failed_constraints:
        status = EligibilityStatus.INELIGIBLE
    elif unknown_constraints:
        status = EligibilityStatus.UNKNOWN
    else:
        status = EligibilityStatus.ELIGIBLE

    return EligibilityResult(
        status=status,
        checks=checks,
        failed_constraints=failed_constraints,
        unknown_constraints=unknown_constraints,
        reasons=reasons,
        engine_version=ENGINE_VERSION,
    )


# ---------------------------------------------------------------------------
# Employment type
# ---------------------------------------------------------------------------


def _check_employment_type(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityCheck:
    allowed = [
        employment_type.strip().lower()
        for employment_type in (criteria.allowed_employment_types or [])
        if employment_type and employment_type.strip()
    ]

    if not allowed:
        return EligibilityCheck(
            constraint="employment_type",
            status=ConstraintStatus.NOT_APPLICABLE,
            reason="No hard employment-type restriction is configured.",
        )

    if not job.employment_type:
        return EligibilityCheck(
            constraint="employment_type",
            status=ConstraintStatus.UNKNOWN,
            reason="Job does not disclose an employment type.",
        )

    if job.employment_type.strip().lower() in allowed:
        return EligibilityCheck(
            constraint="employment_type",
            status=ConstraintStatus.PASS,
            reason=f"Employment type '{job.employment_type}' is accepted.",
        )

    return EligibilityCheck(
        constraint="employment_type",
        status=ConstraintStatus.FAIL,
        reason=(
            f"Employment type '{job.employment_type}' is not in your "
            f"accepted list ({', '.join(allowed)})."
        ),
    )


# ---------------------------------------------------------------------------
# Remote / hybrid / on-site arrangement
# ---------------------------------------------------------------------------


def _check_remote_arrangement(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityCheck:
    required = criteria.required_remote_type

    if not required or not required.strip():
        return EligibilityCheck(
            constraint="remote_arrangement",
            status=ConstraintStatus.NOT_APPLICABLE,
            reason="No hard remote-arrangement restriction is configured.",
        )

    if not job.remote_type:
        return EligibilityCheck(
            constraint="remote_arrangement",
            status=ConstraintStatus.UNKNOWN,
            reason="Job does not disclose a remote work arrangement.",
        )

    if job.remote_type.strip().lower() == required.strip().lower():
        return EligibilityCheck(
            constraint="remote_arrangement",
            status=ConstraintStatus.PASS,
            reason=(
                f"Remote arrangement '{job.remote_type}' matches your "
                f"requirement."
            ),
        )

    return EligibilityCheck(
        constraint="remote_arrangement",
        status=ConstraintStatus.FAIL,
        reason=(
            f"Remote arrangement '{job.remote_type}' does not match your "
            f"required '{required}'."
        ),
    )


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


def _check_location(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityCheck:
    included = [
        location
        for location in (criteria.included_locations or [])
        if location and location.strip()
    ]

    excluded = [
        location
        for location in (criteria.excluded_locations or [])
        if location and location.strip()
    ]

    if not included and not excluded:
        return EligibilityCheck(
            constraint="location",
            status=ConstraintStatus.NOT_APPLICABLE,
            reason="No hard location restriction is configured.",
        )

    # A blank or punctuation-only location (e.g. "   " or ",,") is
    # malformed source data that carries no more information than a
    # missing one — treat both as UNKNOWN rather than letting substring
    # matching semantics (or a spurious "no match" FAIL) decide the
    # outcome.
    if not job.location or not job.location.strip(" ,"):
        return EligibilityCheck(
            constraint="location",
            status=ConstraintStatus.UNKNOWN,
            reason="Job does not disclose a location.",
        )

    for excluded_location in excluded:
        if location_token_matches(excluded_location, job.location):
            return EligibilityCheck(
                constraint="location",
                status=ConstraintStatus.FAIL,
                reason=(
                    f"Job location '{job.location}' matches your excluded "
                    f"location '{excluded_location}'."
                ),
            )

    if included:
        for accepted_location in included:
            if location_token_matches(accepted_location, job.location):
                return EligibilityCheck(
                    constraint="location",
                    status=ConstraintStatus.PASS,
                    reason=(
                        f"Job location '{job.location}' matches accepted "
                        f"location '{accepted_location}'."
                    ),
                )

        return EligibilityCheck(
            constraint="location",
            status=ConstraintStatus.FAIL,
            reason=(
                f"Job location '{job.location}' does not match any of "
                f"your accepted locations ({', '.join(included)})."
            ),
        )

    return EligibilityCheck(
        constraint="location",
        status=ConstraintStatus.PASS,
        reason=f"Job location '{job.location}' does not match any excluded location.",
    )


# ---------------------------------------------------------------------------
# Work authorization
# ---------------------------------------------------------------------------


def _check_sponsorship(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityCheck:
    if criteria.requires_sponsorship is None:
        return EligibilityCheck(
            constraint="sponsorship",
            status=ConstraintStatus.NOT_APPLICABLE,
            reason="No sponsorship requirement is configured.",
        )

    if criteria.requires_sponsorship is False:
        return EligibilityCheck(
            constraint="sponsorship",
            status=ConstraintStatus.PASS,
            reason="You indicated you do not require visa sponsorship.",
        )

    signals = job.work_authorization

    if signals.sponsorship_available is True:
        return EligibilityCheck(
            constraint="sponsorship",
            status=ConstraintStatus.PASS,
            reason="Job states visa sponsorship is available.",
        )

    if signals.sponsorship_available is False:
        return EligibilityCheck(
            constraint="sponsorship",
            status=ConstraintStatus.FAIL,
            reason=(
                "Job states visa sponsorship is not available, and you "
                "require sponsorship."
            ),
        )

    if signals.authorization_required:
        return EligibilityCheck(
            constraint="sponsorship",
            status=ConstraintStatus.FAIL,
            reason=(
                "Job requires candidates already authorized to work in "
                "the U.S., and you require sponsorship."
            ),
        )

    return EligibilityCheck(
        constraint="sponsorship",
        status=ConstraintStatus.UNKNOWN,
        reason=(
            "Job does not disclose a sponsorship or work-authorization "
            "requirement."
        ),
    )


def _check_citizenship(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityCheck:
    if not job.work_authorization.citizenship_required:
        return EligibilityCheck(
            constraint="citizenship",
            status=ConstraintStatus.NOT_APPLICABLE,
            reason="Job does not state a citizenship requirement.",
        )

    if criteria.is_us_citizen is None:
        return EligibilityCheck(
            constraint="citizenship",
            status=ConstraintStatus.UNKNOWN,
            reason=(
                "Job requires U.S. citizenship, and your citizenship "
                "status is not set."
            ),
        )

    if criteria.is_us_citizen:
        return EligibilityCheck(
            constraint="citizenship",
            status=ConstraintStatus.PASS,
            reason="Job requires U.S. citizenship, which you have indicated.",
        )

    return EligibilityCheck(
        constraint="citizenship",
        status=ConstraintStatus.FAIL,
        reason=(
            "Job requires U.S. citizenship, which you have indicated you "
            "do not have."
        ),
    )


def _check_security_clearance(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityCheck:
    if not job.work_authorization.clearance_required:
        return EligibilityCheck(
            constraint="security_clearance",
            status=ConstraintStatus.NOT_APPLICABLE,
            reason="Job does not state a security clearance requirement.",
        )

    if criteria.has_security_clearance is None:
        return EligibilityCheck(
            constraint="security_clearance",
            status=ConstraintStatus.UNKNOWN,
            reason=(
                "Job requires a security clearance, and your clearance "
                "status is not set."
            ),
        )

    if criteria.has_security_clearance:
        return EligibilityCheck(
            constraint="security_clearance",
            status=ConstraintStatus.PASS,
            reason=(
                "Job requires a security clearance, which you have "
                "indicated you hold."
            ),
        )

    return EligibilityCheck(
        constraint="security_clearance",
        status=ConstraintStatus.FAIL,
        reason=(
            "Job requires a security clearance, which you have indicated "
            "you do not hold."
        ),
    )


# ---------------------------------------------------------------------------
# Experience (opt-in hard minimum only)
# ---------------------------------------------------------------------------


def _check_experience(
    criteria: UserEligibilityCriteria,
    job: JobEligibilitySignals,
) -> EligibilityCheck:
    if not criteria.enforce_minimum_experience:
        return EligibilityCheck(
            constraint="experience",
            status=ConstraintStatus.NOT_APPLICABLE,
            reason="Hard minimum-experience enforcement is not enabled.",
        )

    if job.minimum_years_required is None:
        return EligibilityCheck(
            constraint="experience",
            status=ConstraintStatus.UNKNOWN,
            reason=(
                "Job does not disclose a minimum years-of-experience "
                "requirement."
            ),
        )

    if criteria.user_years_experience is None:
        return EligibilityCheck(
            constraint="experience",
            status=ConstraintStatus.UNKNOWN,
            reason="Your years of experience is not set in your profile.",
        )

    if criteria.user_years_experience >= job.minimum_years_required:
        return EligibilityCheck(
            constraint="experience",
            status=ConstraintStatus.PASS,
            reason=(
                f"Your {criteria.user_years_experience} years of "
                f"experience meets the job's "
                f"{job.minimum_years_required}-year requirement."
            ),
        )

    return EligibilityCheck(
        constraint="experience",
        status=ConstraintStatus.FAIL,
        reason=(
            f"Your {criteria.user_years_experience} years of experience "
            f"is below the job's {job.minimum_years_required}-year "
            f"requirement."
        ),
    )
