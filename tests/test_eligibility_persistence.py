from uuid import uuid4

from apps.api.models import Company, Job, JobEligibilityResult, Preference, Profile, User
from apps.api.services.eligibility_service import (
    evaluate_and_persist_job_eligibility,
)
from services.eligibility.contracts import EligibilityStatus


def _make_user(db, **preference_kwargs):
    user = User(
        id=uuid4(),
        email=f"eligibility-persist-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id))

    if preference_kwargs:
        db.add(Preference(id=uuid4(), user_id=user.id, **preference_kwargs))

    db.flush()

    return user


def _make_job(db, **kwargs):
    company = Company(
        id=uuid4(),
        name="Eligibility Persistence Test Co",
        normalized_name="eligibility persistence test co",
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


def test_evaluate_and_persist_creates_a_row(db):
    user = _make_user(db, employment_types=["full_time"])
    job = _make_job(db, employment_type="full_time")

    result, record = evaluate_and_persist_job_eligibility(
        db=db, current_user=user, job=job,
    )

    assert result.status == EligibilityStatus.ELIGIBLE

    stored = (
        db.query(JobEligibilityResult)
        .filter(
            JobEligibilityResult.user_id == user.id,
            JobEligibilityResult.job_id == job.id,
        )
        .first()
    )

    assert stored is not None
    assert stored.id == record.id
    assert stored.status == "eligible"
    assert stored.engine_version == result.engine_version
    assert stored.result["failed_constraints"] == []


def test_repeated_evaluation_upserts_the_same_row(db):
    user = _make_user(db, employment_types=["contract"])
    job = _make_job(db, employment_type="full_time")

    _, first_record = evaluate_and_persist_job_eligibility(
        db=db, current_user=user, job=job,
    )

    assert first_record.status == "ineligible"

    # Preference relaxes: the same job now becomes eligible. Re-evaluating
    # must update the existing row in place, never insert a second one.
    user.preferences.employment_types = ["contract", "full_time"]
    db.flush()

    _, second_record = evaluate_and_persist_job_eligibility(
        db=db, current_user=user, job=job,
    )

    assert second_record.id == first_record.id
    assert second_record.status == "eligible"

    rows = (
        db.query(JobEligibilityResult)
        .filter(
            JobEligibilityResult.user_id == user.id,
            JobEligibilityResult.job_id == job.id,
        )
        .all()
    )

    assert len(rows) == 1


def test_two_users_get_independent_persisted_rows_for_the_same_job(db):
    contract_only_user = _make_user(db, employment_types=["contract"])
    full_time_only_user = _make_user(db, employment_types=["full_time"])

    job = _make_job(db, employment_type="contract")

    evaluate_and_persist_job_eligibility(
        db=db, current_user=contract_only_user, job=job,
    )
    evaluate_and_persist_job_eligibility(
        db=db, current_user=full_time_only_user, job=job,
    )

    rows = (
        db.query(JobEligibilityResult)
        .filter(JobEligibilityResult.job_id == job.id)
        .all()
    )

    assert len(rows) == 2

    by_user = {row.user_id: row for row in rows}

    assert by_user[contract_only_user.id].status == "eligible"
    assert by_user[full_time_only_user.id].status == "ineligible"
