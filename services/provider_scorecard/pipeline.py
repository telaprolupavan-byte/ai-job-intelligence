from __future__ import annotations

import time

from services.job_discovery.deduplicator import build_job_fingerprint
from services.job_discovery.validator import JobValidationError, validate_discovered_job
from services.provider_scorecard.adapter import ProviderSearchAdapter
from services.provider_scorecard.contracts import (
    ProviderScorecard,
    ScenarioMeasurement,
    SearchScenario,
)
from services.provider_scorecard.metrics import compute_field_completeness, compute_rate
from services.provider_scorecard.normalize import normalize_candidate_job


def run_scenario(
    adapter: ProviderSearchAdapter,
    scenario: SearchScenario,
) -> ScenarioMeasurement:
    """
    Raw results -> normalize -> deduplicate -> measure for one
    (provider, scenario) pair. Never raises: an adapter failure is captured
    as a failed measurement so one bad scenario doesn't abort a whole
    provider comparison.
    """

    started_at = time.perf_counter()

    try:
        raw_jobs = adapter.search(scenario)
    except Exception as exc:  # noqa: BLE001 - isolate per-scenario adapter failures
        return ScenarioMeasurement(
            provider=adapter.provider_name,
            scenario_id=scenario.scenario_id,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            error=str(exc),
        )

    latency_ms = (time.perf_counter() - started_at) * 1000

    normalized_jobs = [normalize_candidate_job(job) for job in raw_jobs]

    fingerprints = [build_job_fingerprint(job) for job in normalized_jobs]
    unique_count = len(set(fingerprints))
    duplicate_count = len(normalized_jobs) - unique_count

    invalid_count = 0
    for job in normalized_jobs:
        try:
            validate_discovered_job(job)
        except JobValidationError:
            invalid_count += 1

    valid_count = len(normalized_jobs) - invalid_count

    return ScenarioMeasurement(
        provider=adapter.provider_name,
        scenario_id=scenario.scenario_id,
        fetched_count=len(normalized_jobs),
        unique_count=unique_count,
        duplicate_count=duplicate_count,
        duplicate_rate=compute_rate(duplicate_count, len(normalized_jobs)),
        valid_count=valid_count,
        invalid_count=invalid_count,
        validation_pass_rate=compute_rate(valid_count, len(normalized_jobs)),
        field_completeness=compute_field_completeness(normalized_jobs),
        latency_ms=latency_ms,
    )


def run_provider_scorecard(
    adapter: ProviderSearchAdapter,
    scenarios: list[SearchScenario],
) -> ProviderScorecard:
    """
    Run every scenario in ``scenarios`` against one provider and aggregate
    the result. Callers comparing multiple providers should pass the exact
    same ``scenarios`` list to each call - that shared input is what makes
    the resulting scorecards comparable at all.
    """

    return ProviderScorecard(
        provider=adapter.provider_name,
        scenario_measurements=[
            run_scenario(adapter, scenario) for scenario in scenarios
        ],
    )


def compare_providers(
    adapters: list[ProviderSearchAdapter],
    scenarios: list[SearchScenario],
) -> list[ProviderScorecard]:
    """Run the same scenario set against each of ``adapters``."""

    return [run_provider_scorecard(adapter, scenarios) for adapter in adapters]
