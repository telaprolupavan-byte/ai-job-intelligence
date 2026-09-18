import pytest

from services.provider_scorecard.contracts import ProviderScorecard, ScenarioMeasurement


def test_scorecard_aggregates_are_weighted_by_fetched_count():
    scorecard = ProviderScorecard(
        provider="fake-provider",
        scenario_measurements=[
            ScenarioMeasurement(
                provider="fake-provider",
                scenario_id="a",
                fetched_count=10,
                duplicate_rate=0.5,
                validation_pass_rate=1.0,
                latency_ms=100.0,
                field_completeness={"title": 1.0},
            ),
            ScenarioMeasurement(
                provider="fake-provider",
                scenario_id="b",
                fetched_count=90,
                duplicate_rate=0.0,
                validation_pass_rate=0.5,
                latency_ms=300.0,
                field_completeness={"title": 0.0},
            ),
        ],
    )

    assert scorecard.overall_duplicate_rate == pytest.approx(0.05)
    assert scorecard.overall_validation_pass_rate == pytest.approx(0.55)
    assert scorecard.average_latency_ms == pytest.approx(200.0)
    assert scorecard.average_field_completeness["title"] == pytest.approx(0.1)


def test_scorecard_excludes_failed_scenarios_from_weighted_aggregates():
    scorecard = ProviderScorecard(
        provider="fake-provider",
        scenario_measurements=[
            ScenarioMeasurement(
                provider="fake-provider",
                scenario_id="a",
                fetched_count=10,
                duplicate_rate=0.5,
                validation_pass_rate=1.0,
            ),
            ScenarioMeasurement(
                provider="fake-provider",
                scenario_id="b",
                error="timeout",
            ),
        ],
    )

    assert scorecard.scenarios_with_errors == ["b"]
    # Only the succeeded scenario contributes - the failed one has no
    # measured rate to average in, not a 0.0 that would silently drag the
    # aggregate down.
    assert scorecard.overall_duplicate_rate == pytest.approx(0.5)
    assert scorecard.overall_validation_pass_rate == pytest.approx(1.0)


def test_scorecard_with_no_measurements_has_zeroed_aggregates():
    scorecard = ProviderScorecard(provider="fake-provider")

    assert scorecard.total_fetched == 0
    assert scorecard.total_unique == 0
    assert scorecard.overall_duplicate_rate == 0.0
    assert scorecard.overall_validation_pass_rate == 0.0
    assert scorecard.average_latency_ms == 0.0
    assert scorecard.average_field_completeness == {}
