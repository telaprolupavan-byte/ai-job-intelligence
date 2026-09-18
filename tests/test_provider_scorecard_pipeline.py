import pytest

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.contracts import SearchScenario
from services.provider_scorecard.pipeline import (
    compare_providers,
    run_provider_scorecard,
    run_scenario,
)


def _job(
    source_job_id="1",
    title="Backend Engineer",
    company="Example Inc",
    location="New York, NY",
    country="USA",
    remote_type="Remote",
    employment_type="Full-Time",
    description="Build things.",
    source_url="https://example.test/jobs/1",
    application_url="https://example.test/jobs/1",
):
    return DiscoveredJob(
        source="fake-provider",
        source_job_id=source_job_id,
        title=title,
        company=company,
        description=description,
        requirements=None,
        responsibilities=None,
        location=location,
        country=country,
        remote_type=remote_type,
        employment_type=employment_type,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url=source_url,
        application_url=application_url,
        posted_at=None,
        expires_at=None,
    )


class _FakeAdapter:
    def __init__(self, provider_name, jobs_by_scenario=None, error=None):
        self.provider_name = provider_name
        self._jobs_by_scenario = jobs_by_scenario or {}
        self._error = error
        self.seen_scenarios = []

    def search(self, scenario):
        self.seen_scenarios.append(scenario)

        if self._error is not None:
            raise self._error

        return self._jobs_by_scenario.get(scenario.scenario_id, [])


SCENARIO = SearchScenario(
    scenario_id="backend-remote",
    description="Backend engineer, remote",
    keywords="backend engineer",
    remote_preference="remote",
)


def test_run_scenario_counts_unique_jobs_with_no_duplicates():
    adapter = _FakeAdapter(
        "fake-provider",
        {SCENARIO.scenario_id: [_job("1"), _job("2")]},
    )

    measurement = run_scenario(adapter, SCENARIO)

    assert measurement.provider == "fake-provider"
    assert measurement.scenario_id == SCENARIO.scenario_id
    assert measurement.fetched_count == 2
    assert measurement.unique_count == 2
    assert measurement.duplicate_count == 0
    assert measurement.duplicate_rate == 0.0
    assert measurement.error is None
    assert measurement.succeeded is True


def test_run_scenario_counts_duplicates_by_fingerprint():
    adapter = _FakeAdapter(
        "fake-provider",
        {SCENARIO.scenario_id: [_job("1"), _job("1"), _job("2")]},
    )

    measurement = run_scenario(adapter, SCENARIO)

    assert measurement.fetched_count == 3
    assert measurement.unique_count == 2
    assert measurement.duplicate_count == 1
    assert measurement.duplicate_rate == pytest.approx(1 / 3)


def test_run_scenario_normalizes_before_measuring():
    adapter = _FakeAdapter(
        "fake-provider",
        {
            SCENARIO.scenario_id: [
                _job("1", remote_type="Fully Remote", employment_type="full time")
            ]
        },
    )

    measurement = run_scenario(adapter, SCENARIO)

    # Normalization happening is observable through validation/completeness
    # passing even though the raw adapter data used un-normalized casing.
    assert measurement.valid_count == 1
    assert measurement.field_completeness["remote_type"] == 1.0
    assert measurement.field_completeness["employment_type"] == 1.0


def test_run_scenario_counts_invalid_jobs_without_dropping_them():
    adapter = _FakeAdapter(
        "fake-provider",
        {
            SCENARIO.scenario_id: [
                _job("1"),
                _job("2", country="Germany"),
                _job("3", title=""),
            ]
        },
    )

    measurement = run_scenario(adapter, SCENARIO)

    assert measurement.fetched_count == 3
    assert measurement.valid_count == 1
    assert measurement.invalid_count == 2
    assert measurement.validation_pass_rate == pytest.approx(1 / 3)


def test_run_scenario_measures_field_completeness():
    adapter = _FakeAdapter(
        "fake-provider",
        {
            SCENARIO.scenario_id: [
                _job("1", description="Has description."),
                _job("2", description=None),
            ]
        },
    )

    measurement = run_scenario(adapter, SCENARIO)

    assert measurement.field_completeness["description"] == 0.5
    assert measurement.field_completeness["title"] == 1.0


def test_run_scenario_captures_adapter_failure_without_raising():
    adapter = _FakeAdapter("flaky-provider", error=RuntimeError("upstream 500"))

    measurement = run_scenario(adapter, SCENARIO)

    assert measurement.succeeded is False
    assert measurement.error == "upstream 500"
    assert measurement.fetched_count == 0


def test_run_provider_scorecard_runs_every_scenario_once():
    scenario_two = SearchScenario(
        scenario_id="frontend-nyc",
        description="Frontend engineer, NYC",
        keywords="frontend engineer",
        location="New York, NY",
    )

    adapter = _FakeAdapter(
        "fake-provider",
        {
            SCENARIO.scenario_id: [_job("1")],
            scenario_two.scenario_id: [_job("2"), _job("3")],
        },
    )

    scorecard = run_provider_scorecard(adapter, [SCENARIO, scenario_two])

    assert scorecard.provider == "fake-provider"
    assert [m.scenario_id for m in scorecard.scenario_measurements] == [
        SCENARIO.scenario_id,
        scenario_two.scenario_id,
    ]
    assert scorecard.total_fetched == 3
    assert scorecard.total_unique == 3
    assert scorecard.scenarios_with_errors == []


def test_provider_scorecard_excludes_failed_scenarios_from_rate_aggregates():
    adapter = _FakeAdapter(
        "flaky-provider",
        error=RuntimeError("timeout"),
    )

    scorecard = run_provider_scorecard(adapter, [SCENARIO])

    assert scorecard.scenarios_with_errors == [SCENARIO.scenario_id]
    assert scorecard.overall_duplicate_rate == 0.0
    assert scorecard.overall_validation_pass_rate == 0.0
    assert scorecard.average_latency_ms == 0.0


def test_compare_providers_runs_the_same_scenarios_against_each_adapter():
    adapter_a = _FakeAdapter("provider-a", {SCENARIO.scenario_id: [_job("1")]})
    adapter_b = _FakeAdapter("provider-b", {SCENARIO.scenario_id: [_job("2")]})

    scorecards = compare_providers([adapter_a, adapter_b], [SCENARIO])

    assert [s.provider for s in scorecards] == ["provider-a", "provider-b"]
    assert adapter_a.seen_scenarios == [SCENARIO]
    assert adapter_b.seen_scenarios == [SCENARIO]
