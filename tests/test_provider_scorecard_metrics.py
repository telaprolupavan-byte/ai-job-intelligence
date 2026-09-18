from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.metrics import compute_field_completeness, compute_rate


def _job(**overrides):
    base = dict(
        source="fake-provider",
        source_job_id="1",
        title="Backend Engineer",
        company="Example Inc",
        description="Build things.",
        requirements=None,
        responsibilities=None,
        location="New York, NY",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
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


def test_compute_field_completeness_empty_job_list():
    result = compute_field_completeness([], fields=("title", "description"))

    assert result == {"title": 0.0, "description": 0.0}


def test_compute_field_completeness_counts_blank_strings_as_missing():
    jobs = [_job(description="Real content."), _job(description="   ")]

    result = compute_field_completeness(jobs, fields=("description",))

    assert result["description"] == 0.5


def test_compute_field_completeness_counts_none_as_missing():
    jobs = [_job(location="New York, NY"), _job(location=None)]

    result = compute_field_completeness(jobs, fields=("location",))

    assert result["location"] == 0.5


def test_compute_rate_zero_total_returns_zero():
    assert compute_rate(0, 0) == 0.0


def test_compute_rate_normal_division():
    assert compute_rate(1, 4) == 0.25
