from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchScenario:
    """
    One reusable search scenario in the fixed, shared set run identically
    against every candidate provider ("Same NERO search scenarios" in the
    workflow diagram). Fairness of the comparison depends on every
    provider seeing the exact same ``scenario_id``/``keywords``/
    ``location``/``remote_preference`` — never a provider-specific query.
    """

    scenario_id: str
    description: str
    keywords: str
    location: str | None = None
    remote_preference: str | None = None


@dataclass
class ScenarioMeasurement:
    """
    Objective, descriptive metrics for one (provider, scenario) run.
    Deliberately produces no verdict/recommendation of its own — see
    ``ProviderScorecard``.
    """

    provider: str
    scenario_id: str

    fetched_count: int = 0
    unique_count: int = 0
    duplicate_count: int = 0
    duplicate_rate: float = 0.0

    valid_count: int = 0
    invalid_count: int = 0
    validation_pass_rate: float = 0.0

    field_completeness: dict[str, float] = field(default_factory=dict)

    latency_ms: float = 0.0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass
class ProviderScorecard:
    """
    The aggregate result of running every ``SearchScenario`` in a
    comparison set against one provider. This is input to a Product
    Owner's implementation decision, not the decision itself — no field
    here ranks or recommends a provider.
    """

    provider: str
    scenario_measurements: list[ScenarioMeasurement] = field(default_factory=list)

    @property
    def total_fetched(self) -> int:
        return sum(m.fetched_count for m in self.scenario_measurements)

    @property
    def total_unique(self) -> int:
        return sum(m.unique_count for m in self.scenario_measurements)

    @property
    def scenarios_with_errors(self) -> list[str]:
        return [m.scenario_id for m in self.scenario_measurements if not m.succeeded]

    @property
    def overall_duplicate_rate(self) -> float:
        return _weighted_average(
            (m.duplicate_rate, m.fetched_count)
            for m in self.scenario_measurements
            if m.succeeded
        )

    @property
    def overall_validation_pass_rate(self) -> float:
        return _weighted_average(
            (m.validation_pass_rate, m.fetched_count)
            for m in self.scenario_measurements
            if m.succeeded
        )

    @property
    def average_latency_ms(self) -> float:
        succeeded = [m.latency_ms for m in self.scenario_measurements if m.succeeded]

        if not succeeded:
            return 0.0

        return sum(succeeded) / len(succeeded)

    @property
    def average_field_completeness(self) -> dict[str, float]:
        succeeded = [m for m in self.scenario_measurements if m.succeeded]

        fields: set[str] = set()
        for measurement in succeeded:
            fields.update(measurement.field_completeness)

        return {
            field_name: _weighted_average(
                (m.field_completeness.get(field_name, 0.0), m.fetched_count)
                for m in succeeded
            )
            for field_name in sorted(fields)
        }


def _weighted_average(pairs) -> float:
    total_weight = 0
    total_value = 0.0

    for value, weight in pairs:
        total_value += value * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return total_value / total_weight
