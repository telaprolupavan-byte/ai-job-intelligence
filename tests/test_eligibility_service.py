from uuid import uuid4

from apps.api.models import Company, Job, Preference, Profile, User
from apps.api.services.eligibility_service import (
    evaluate_job_eligibility,
    evaluate_jobs_eligibility,
)
from services.eligibility.contracts import EligibilityStatus


def _make_user(db, **preference_kwargs):
    user = User(
        id=uuid4(),
        email=f"eligibility-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    profile = Profile(
        id=uuid4(),
        user_id=user.id,
        years_experience=preference_kwargs.pop("years_experience", None),
    )
    db.add(profile)

    preference = Preference(
        id=uuid4(),
        user_id=user.id,
        **preference_kwargs,
    )
    db.add(preference)
    db.flush()

    return user


def _make_job(db, **kwargs):
    company = Company(
        id=uuid4(),
        name="Eligibility Test Co",
        normalized_name="eligibility test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Software Engineer",
        source="test",
        **kwargs,
    )
    db.add(job)
    db.flush()

    return job


def test_evaluate_job_eligibility_uses_current_user_preferences(db):
    user = _make_user(db, employment_types=["contract"])
    job = _make_job(db, employment_type="full_time")

    result = evaluate_job_eligibility(current_user=user, job=job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "employment_type" in result.failed_constraints


def test_evaluate_job_eligibility_no_preferences_is_eligible(db):
    user = User(
        id=uuid4(),
        email=f"no-prefs-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    job = _make_job(db, employment_type="contract")

    result = evaluate_job_eligibility(current_user=user, job=job)

    assert result.status == EligibilityStatus.ELIGIBLE


def test_evaluate_job_eligibility_experience_uses_job_text(db):
    user = _make_user(
        db,
        enforce_minimum_experience=True,
        years_experience=2,
    )
    job = _make_job(
        db,
        requirements="5+ years of experience with Python required.",
    )

    result = evaluate_job_eligibility(current_user=user, job=job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "experience" in result.failed_constraints


def test_evaluate_job_eligibility_sponsorship_signal_from_job_text(db):
    user = _make_user(db, requires_sponsorship=True)
    job = _make_job(
        db,
        description="We are unable to offer visa sponsorship for this role.",
    )

    result = evaluate_job_eligibility(current_user=user, job=job)

    assert result.status == EligibilityStatus.INELIGIBLE
    assert "sponsorship" in result.failed_constraints


def test_evaluate_jobs_eligibility_builds_criteria_once_per_call(db):
    user = _make_user(db, employment_types=["full_time"])

    matching_job = _make_job(db, employment_type="full_time")
    mismatching_job = _make_job(db, employment_type="contract")

    results = evaluate_jobs_eligibility(
        current_user=user,
        jobs=[matching_job, mismatching_job],
    )

    assert results[matching_job.id].status == EligibilityStatus.ELIGIBLE
    assert results[mismatching_job.id].status == EligibilityStatus.INELIGIBLE


def test_two_users_get_independent_eligibility_for_the_same_job(db):
    contract_only_user = _make_user(db, employment_types=["contract"])
    full_time_only_user = _make_user(db, employment_types=["full_time"])

    job = _make_job(db, employment_type="contract")

    contract_user_result = evaluate_job_eligibility(
        current_user=contract_only_user,
        job=job,
    )
    full_time_user_result = evaluate_job_eligibility(
        current_user=full_time_only_user,
        job=job,
    )

    assert contract_user_result.status == EligibilityStatus.ELIGIBLE
    assert full_time_user_result.status == EligibilityStatus.INELIGIBLE
