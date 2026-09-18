from datetime import datetime, timezone

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.report import (
    REPORT_ROWS,
    build_provider_report,
    render_markdown_table,
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
        remote_type="Remote",
        employment_type="Full-Time",
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url="https://example.test/1",
        application_url="https://example.test/1",
        posted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        expires_at=None,
    )
    base.update(overrides)
    return DiscoveredJob(**base)


def test_build_provider_report_counts_raw_valid_unique():
    raw_jobs_by_scenario = {
        "scenario-a": [_job(source_job_id="1"), _job(source_job_id="2")],
        "scenario-b": [_job(source_job_id="2")],  # overlaps with scenario-a
    }

    report = build_provider_report("fake-provider", raw_jobs_by_scenario)

    assert report.raw_jobs == 3
    # source_job_id "2" appears twice across scenarios - global dedup
    # must collapse it to one, not count it once per scenario.
    assert report.unique_jobs == 2
    assert report.duplicate_rate == 1 / 3


def test_build_provider_report_counts_valid_jobs_via_shared_validator():
    raw_jobs_by_scenario = {
        "scenario-a": [_job(source_job_id="1"), _job(source_job_id="2", country="Germany")],
    }

    report = build_provider_report("fake-provider", raw_jobs_by_scenario)

    assert report.raw_jobs == 2
    assert report.valid_jobs == 1


def test_build_provider_report_normalizes_before_measuring_job_type_counts():
    raw_jobs_by_scenario = {
        "scenario-a": [
            _job(source_job_id="1", employment_type="Full-Time", remote_type="Fully Remote"),
            _job(source_job_id="2", employment_type="Contract", remote_type="On-Site"),
        ],
    }

    report = build_provider_report("fake-provider", raw_jobs_by_scenario)

    assert report.ft_jobs == 1
    assert report.contract_jobs == 1
    assert report.remote_jobs == 1


def test_build_provider_report_ai_ml_and_salary_and_application_url():
    raw_jobs_by_scenario = {
        "scenario-a": [
            _job(source_job_id="1", title="Machine Learning Engineer", salary_min=100000),
            _job(source_job_id="2", title="Backend Engineer", application_url=None),
        ],
    }

    report = build_provider_report("fake-provider", raw_jobs_by_scenario)

    assert report.ai_ml_jobs == 1
    assert report.salary_available_rate == 0.5
    assert report.application_url_rate == 0.5


def test_build_provider_report_reliability_counts_error_scenarios():
    raw_jobs_by_scenario = {"scenario-a": [_job(source_job_id="1")]}
    errors_by_scenario = {"scenario-b": "HTTP 429 Too Many Requests"}

    report = build_provider_report(
        "fake-provider", raw_jobs_by_scenario, errors_by_scenario=errors_by_scenario
    )

    assert report.total_scenarios == 2
    assert report.successful_scenarios == 1
    assert report.reliability_rate == 0.5
    assert report.scenario_errors == {"scenario-b": "HTTP 429 Too Many Requests"}


def test_build_provider_report_reliability_is_none_with_no_attempts():
    report = build_provider_report("fake-provider", {})

    assert report.total_scenarios == 0
    assert report.reliability_rate is None
    assert report.raw_jobs == 0
    assert report.unique_jobs == 0


def test_build_provider_report_freshness_none_without_posted_at():
    raw_jobs_by_scenario = {"scenario-a": [_job(source_job_id="1", posted_at=None)]}

    report = build_provider_report("fake-provider", raw_jobs_by_scenario)

    assert report.freshness_days is None


def test_render_markdown_table_has_one_column_per_provider_and_every_row():
    report_a = build_provider_report("provider-a", {"s": [_job(source_job_id="1")]})
    report_b = build_provider_report("provider-b", {"s": [_job(source_job_id="2")]})

    table = render_markdown_table([report_a, report_b])

    header_line = table.splitlines()[0]
    assert "provider-a" in header_line
    assert "provider-b" in header_line

    for row_label in REPORT_ROWS:
        assert row_label in table


def test_render_markdown_table_includes_no_score_or_winner_column():
    report = build_provider_report("provider-a", {"s": [_job(source_job_id="1")]})

    table = render_markdown_table([report])

    lowered = table.lower()
    assert "score" not in lowered
    assert "winner" not in lowered
    assert "rank" not in lowered


def test_render_markdown_table_surfaces_scenario_errors():
    report = build_provider_report(
        "flaky-provider", {}, errors_by_scenario={"scenario-a": "timeout"}
    )

    table = render_markdown_table([report])

    assert "flaky-provider scenario errors" in table
    assert "scenario-a" in table
    assert "timeout" in table
