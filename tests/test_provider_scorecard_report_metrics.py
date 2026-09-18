from datetime import datetime, timedelta, timezone

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.report_metrics import (
    compute_median_freshness_days,
    count_ai_ml_jobs,
    count_by_employment_type,
    count_remote_jobs,
    count_with_application_url,
    count_with_salary,
    is_ai_ml_job,
)


def _job(**overrides):
    base = dict(
        source="fake",
        source_job_id="1",
        title="Backend Engineer",
        company="Example Inc",
        description="Build things.",
        requirements=None,
        responsibilities=None,
        location="New York, NY",
        country="USA",
        remote_type=None,
        employment_type=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url="https://example.test/1",
        application_url="https://example.test/1",
        posted_at=None,
        expires_at=None,
    )
    base.update(overrides)
    return DiscoveredJob(**base)


def test_is_ai_ml_job_matches_title():
    assert is_ai_ml_job(_job(title="Machine Learning Engineer")) is True


def test_is_ai_ml_job_matches_description_only():
    job = _job(title="Software Engineer II", description="Work on our NLP pipeline.")

    assert is_ai_ml_job(job) is True


def test_is_ai_ml_job_false_for_unrelated_role():
    assert is_ai_ml_job(_job(title="Backend Engineer", description="Build APIs.")) is False


def test_count_ai_ml_jobs():
    jobs = [
        _job(title="Machine Learning Engineer"),
        _job(title="Backend Engineer"),
        _job(title="AI Researcher"),
    ]

    assert count_ai_ml_jobs(jobs) == 2


def test_count_by_employment_type_compares_normalized_value():
    jobs = [
        _job(employment_type="full_time"),
        _job(employment_type="contract"),
        _job(employment_type=None),
    ]

    assert count_by_employment_type(jobs, "full_time") == 1
    assert count_by_employment_type(jobs, "contract") == 1


def test_count_remote_jobs_requires_normalized_remote_value():
    jobs = [_job(remote_type="remote"), _job(remote_type="hybrid"), _job(remote_type=None)]

    assert count_remote_jobs(jobs) == 1


def test_count_with_salary_true_if_either_bound_present():
    jobs = [
        _job(salary_min=50000, salary_max=None),
        _job(salary_min=None, salary_max=90000),
        _job(salary_min=None, salary_max=None),
    ]

    assert count_with_salary(jobs) == 2


def test_count_with_application_url():
    jobs = [_job(application_url="https://example.test/1"), _job(application_url=None)]

    assert count_with_application_url(jobs) == 1


def test_freshness_returns_none_when_no_posted_at():
    jobs = [_job(posted_at=None), _job(posted_at=None)]

    assert compute_median_freshness_days(jobs) is None


def test_freshness_computes_median_age_in_days():
    reference = datetime(2024, 2, 1, tzinfo=timezone.utc)
    jobs = [
        _job(posted_at=datetime(2024, 1, 22, tzinfo=timezone.utc)),  # 10 days
        _job(posted_at=datetime(2024, 1, 12, tzinfo=timezone.utc)),  # 20 days
        _job(posted_at=None),
    ]

    assert compute_median_freshness_days(jobs, reference_date=reference) == 15


def test_freshness_handles_naive_and_aware_datetimes_together():
    reference = datetime(2024, 2, 1, tzinfo=timezone.utc)
    jobs = [
        _job(posted_at=datetime(2024, 1, 22, tzinfo=timezone.utc)),
        _job(posted_at=datetime(2024, 1, 22)),  # naive, e.g. a date-only source
    ]

    # Must not raise comparing aware vs. naive - both reduce to .date().
    assert compute_median_freshness_days(jobs, reference_date=reference) == 10
