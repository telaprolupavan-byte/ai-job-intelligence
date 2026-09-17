from services.eligibility.contracts import (
    ConstraintStatus,
    EligibilityStatus,
    JobEligibilitySignals,
    UserEligibilityCriteria,
    WorkAuthorizationSignals,
)
from services.eligibility.engine import evaluate_eligibility


def _checks_by_constraint(result):
    return {check.constraint: check for check in result.checks}


# ---------------------------------------------------------------------------
# Employment type
# ---------------------------------------------------------------------------


def test_employment_type_full_time_matches_full_time():
    criteria = UserEligibilityCriteria(allowed_employment_types=["full_time"])
    job = JobEligibilitySignals(employment_type="full_time")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert _checks_by_constraint(result)["employment_type"].status == (
        ConstraintStatus.PASS
    )


def test_employment_type_full_time_rejects_contract():
    criteria = UserEligibilityCriteria(allowed_employment_types=["full_time"])
    job = JobEligibilitySignals(employment_type="contract")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "employment_type" in result.failed_constraints


def test_employment_type_contract_matches_contract():
    criteria = UserEligibilityCriteria(allowed_employment_types=["contract"])
    job = JobEligibilitySignals(employment_type="contract")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_employment_type_contract_rejects_full_time():
    criteria = UserEligibilityCriteria(allowed_employment_types=["contract"])
    job = JobEligibilitySignals(employment_type="full_time")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "employment_type" in result.failed_constraints


def test_employment_type_unrestricted_does_not_exclude():
    criteria = UserEligibilityCriteria(allowed_employment_types=None)
    job = JobEligibilitySignals(employment_type="internship")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert _checks_by_constraint(result)["employment_type"].status == (
        ConstraintStatus.NOT_APPLICABLE
    )


def test_employment_type_unknown_job_type_is_unknown():
    criteria = UserEligibilityCriteria(allowed_employment_types=["full_time"])
    job = JobEligibilitySignals(employment_type=None)

    result = evaluate_eligibility(criteria, job)

    # UNKNOWN must never be silently promoted to INELIGIBLE.
    assert result.status == EligibilityStatus.UNKNOWN
    assert "employment_type" in result.unknown_constraints
    assert result.failed_constraints == []


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


def test_location_matching_city_state():
    criteria = UserEligibilityCriteria(included_locations=["Austin, TX"])
    job = JobEligibilitySignals(location="Austin, TX")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_location_mismatch():
    criteria = UserEligibilityCriteria(included_locations=["Seattle, WA"])
    job = JobEligibilitySignals(location="Austin, TX")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "location" in result.failed_constraints


def test_location_excluded_location_is_ineligible():
    criteria = UserEligibilityCriteria(excluded_locations=["California"])
    job = JobEligibilitySignals(location="California")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "location" in result.failed_constraints


def test_location_multiple_accepted_locations_state_resolution():
    # New York / New Jersey should accept a job located in Newark, NJ via
    # state-name/abbreviation resolution, without unsafe fuzzy matching.
    criteria = UserEligibilityCriteria(
        included_locations=["New York", "New Jersey"]
    )
    job = JobEligibilitySignals(location="Newark, NJ")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_location_missing_job_location_is_unknown_not_a_silent_match():
    criteria = UserEligibilityCriteria(included_locations=["New York"])
    job = JobEligibilitySignals(location=None)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "location" in result.unknown_constraints
    assert result.failed_constraints == []


def test_location_missing_job_location_with_only_exclusions_is_unknown():
    # An exclusion list alone (no inclusion list) is still a restrictive,
    # "active" location constraint — missing job location data must still
    # resolve to UNKNOWN, never a silent pass or a silent fail.
    criteria = UserEligibilityCriteria(excluded_locations=["California"])
    job = JobEligibilitySignals(location=None)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "location" in result.unknown_constraints
    assert result.failed_constraints == []


def test_location_unrestricted_does_not_exclude():
    criteria = UserEligibilityCriteria()
    job = JobEligibilitySignals(location=None)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert _checks_by_constraint(result)["location"].status == (
        ConstraintStatus.NOT_APPLICABLE
    )


def test_location_malformed_blank_string_is_unknown_not_a_silent_match():
    # A whitespace-only location is malformed source data, not a real
    # location. Since "" is a substring of every string, this must be
    # treated as UNKNOWN, never as a silent match against every token.
    criteria = UserEligibilityCriteria(included_locations=["New York"])
    job = JobEligibilitySignals(location="   ")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "location" in result.unknown_constraints
    assert result.failed_constraints == []


def test_location_malformed_punctuation_only_is_unknown_not_a_fail():
    # Punctuation-only "location" data (e.g. ",,") is also malformed —
    # it must resolve to UNKNOWN, not a spurious FAIL from "no accepted
    # location matched" reasoning applied to garbage data.
    criteria = UserEligibilityCriteria(included_locations=["New York"])
    job = JobEligibilitySignals(location=",,")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "location" in result.unknown_constraints
    assert result.failed_constraints == []


# ---------------------------------------------------------------------------
# Remote / hybrid / on-site
# ---------------------------------------------------------------------------


def test_remote_only_matches_remote():
    criteria = UserEligibilityCriteria(required_remote_type="remote")
    job = JobEligibilitySignals(remote_type="remote")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_remote_only_rejects_hybrid():
    criteria = UserEligibilityCriteria(required_remote_type="remote")
    job = JobEligibilitySignals(remote_type="hybrid")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "remote_arrangement" in result.failed_constraints


def test_remote_only_rejects_onsite():
    criteria = UserEligibilityCriteria(required_remote_type="remote")
    job = JobEligibilitySignals(remote_type="onsite")

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "remote_arrangement" in result.failed_constraints


def test_remote_only_unknown_job_status_is_unknown():
    criteria = UserEligibilityCriteria(required_remote_type="remote")
    job = JobEligibilitySignals(remote_type=None)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "remote_arrangement" in result.unknown_constraints
    assert result.failed_constraints == []


# ---------------------------------------------------------------------------
# Work authorization: sponsorship
# ---------------------------------------------------------------------------


def test_sponsorship_compatible_when_available():
    criteria = UserEligibilityCriteria(requires_sponsorship=True)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(
            sponsorship_available=True
        )
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_sponsorship_explicit_conflict_when_unavailable():
    criteria = UserEligibilityCriteria(requires_sponsorship=True)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(
            sponsorship_available=False
        )
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "sponsorship" in result.failed_constraints


def test_sponsorship_authorization_required_conflicts_with_sponsorship_need():
    criteria = UserEligibilityCriteria(requires_sponsorship=True)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(
            authorization_required=True
        )
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "sponsorship" in result.failed_constraints


def test_sponsorship_not_required_is_compatible_regardless_of_job():
    criteria = UserEligibilityCriteria(requires_sponsorship=False)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(
            sponsorship_available=False
        )
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_sponsorship_available_does_not_force_ineligibility():
    # A job stating sponsorship is available must never be misread as
    # "sponsorship required of the candidate" — a user who does not need
    # sponsorship stays eligible against such a job.
    criteria = UserEligibilityCriteria(requires_sponsorship=False)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(
            sponsorship_available=True
        )
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert _checks_by_constraint(result)["sponsorship"].status == (
        ConstraintStatus.PASS
    )


def test_sponsorship_unset_preference_is_not_applicable():
    criteria = UserEligibilityCriteria()
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(
            sponsorship_available=False
        )
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert _checks_by_constraint(result)["sponsorship"].status == (
        ConstraintStatus.NOT_APPLICABLE
    )


def test_sponsorship_unknown_when_job_discloses_nothing():
    criteria = UserEligibilityCriteria(requires_sponsorship=True)
    job = JobEligibilitySignals(work_authorization=WorkAuthorizationSignals())

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "sponsorship" in result.unknown_constraints
    assert result.failed_constraints == []


# ---------------------------------------------------------------------------
# Work authorization: citizenship
# ---------------------------------------------------------------------------


def test_citizenship_required_and_user_is_citizen():
    criteria = UserEligibilityCriteria(is_us_citizen=True)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(citizenship_required=True)
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_citizenship_required_and_user_is_not_citizen():
    criteria = UserEligibilityCriteria(is_us_citizen=False)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(citizenship_required=True)
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "citizenship" in result.failed_constraints


def test_citizenship_required_but_unset_is_unknown():
    criteria = UserEligibilityCriteria()
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(citizenship_required=True)
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "citizenship" in result.unknown_constraints
    assert result.failed_constraints == []


def test_citizenship_not_required_is_not_applicable():
    criteria = UserEligibilityCriteria(is_us_citizen=False)
    job = JobEligibilitySignals(work_authorization=WorkAuthorizationSignals())

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert _checks_by_constraint(result)["citizenship"].status == (
        ConstraintStatus.NOT_APPLICABLE
    )


# ---------------------------------------------------------------------------
# Work authorization: security clearance
# ---------------------------------------------------------------------------


def test_clearance_required_and_user_has_clearance():
    criteria = UserEligibilityCriteria(has_security_clearance=True)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(clearance_required=True)
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_clearance_required_and_user_lacks_clearance():
    criteria = UserEligibilityCriteria(has_security_clearance=False)
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(clearance_required=True)
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "security_clearance" in result.failed_constraints


def test_clearance_required_but_unset_is_unknown():
    criteria = UserEligibilityCriteria()
    job = JobEligibilitySignals(
        work_authorization=WorkAuthorizationSignals(clearance_required=True)
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "security_clearance" in result.unknown_constraints
    assert result.failed_constraints == []


# ---------------------------------------------------------------------------
# Experience (opt-in hard minimum only)
# ---------------------------------------------------------------------------


def test_experience_not_enforced_by_default():
    criteria = UserEligibilityCriteria(user_years_experience=1)
    job = JobEligibilitySignals(minimum_years_required=10)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert _checks_by_constraint(result)["experience"].status == (
        ConstraintStatus.NOT_APPLICABLE
    )


def test_experience_below_minimum_when_enforced():
    criteria = UserEligibilityCriteria(
        enforce_minimum_experience=True,
        user_years_experience=2,
    )
    job = JobEligibilitySignals(minimum_years_required=5)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "experience" in result.failed_constraints


def test_experience_meets_minimum_when_enforced():
    criteria = UserEligibilityCriteria(
        enforce_minimum_experience=True,
        user_years_experience=5,
    )
    job = JobEligibilitySignals(minimum_years_required=5)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_experience_unknown_job_requirement_when_enforced():
    criteria = UserEligibilityCriteria(
        enforce_minimum_experience=True,
        user_years_experience=5,
    )
    job = JobEligibilitySignals(minimum_years_required=None)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "experience" in result.unknown_constraints
    assert result.failed_constraints == []


def test_experience_unknown_user_experience_when_enforced():
    criteria = UserEligibilityCriteria(
        enforce_minimum_experience=True,
        user_years_experience=None,
    )
    job = JobEligibilitySignals(minimum_years_required=3)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert "experience" in result.unknown_constraints
    assert result.failed_constraints == []


# ---------------------------------------------------------------------------
# Combinations
# ---------------------------------------------------------------------------


def test_combination_multiple_failed_constraints():
    criteria = UserEligibilityCriteria(
        allowed_employment_types=["full_time"],
        required_remote_type="remote",
    )
    job = JobEligibilitySignals(
        employment_type="contract",
        remote_type="onsite",
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert set(result.failed_constraints) == {
        "employment_type",
        "remote_arrangement",
    }


def test_combination_failed_wins_over_unknown():
    criteria = UserEligibilityCriteria(
        allowed_employment_types=["full_time"],
        required_remote_type="remote",
    )
    job = JobEligibilitySignals(
        employment_type="contract",
        remote_type=None,
    )

    result = evaluate_eligibility(criteria, job)

    # A hard failure must never be masked by an unrelated unknown.
    assert result.status == EligibilityStatus.INELIGIBLE
    assert "employment_type" in result.failed_constraints
    assert "remote_arrangement" in result.unknown_constraints


def test_combination_one_unknown_without_failure_is_overall_unknown():
    criteria = UserEligibilityCriteria(required_remote_type="remote")
    job = JobEligibilitySignals(remote_type=None)

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.UNKNOWN
    assert result.failed_constraints == []
    assert "remote_arrangement" in result.unknown_constraints


def test_combination_all_constraints_satisfied():
    criteria = UserEligibilityCriteria(
        allowed_employment_types=["full_time"],
        included_locations=["Austin, TX"],
        required_remote_type="hybrid",
        requires_sponsorship=False,
    )
    job = JobEligibilitySignals(
        employment_type="full_time",
        location="Austin, TX",
        remote_type="hybrid",
        work_authorization=WorkAuthorizationSignals(),
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert result.failed_constraints == []
    assert result.unknown_constraints == []


def test_combination_unrestricted_user_is_always_eligible():
    criteria = UserEligibilityCriteria()
    job = JobEligibilitySignals(
        employment_type=None,
        location=None,
        remote_type=None,
    )

    result = evaluate_eligibility(criteria, job)

    assert result.status == EligibilityStatus.ELIGIBLE
    assert all(
        check.status == ConstraintStatus.NOT_APPLICABLE
        for check in result.checks
    )
