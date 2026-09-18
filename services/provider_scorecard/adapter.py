from __future__ import annotations

from typing import Protocol

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.contracts import SearchScenario


class ProviderSearchAdapter(Protocol):
    """
    A candidate provider under evaluation. Unlike
    ``services.job_discovery.sources.base.JobSourceAdapter`` (which fetches
    a whole board and is expected to already return normalized data), this
    adapter is queried per ``SearchScenario`` and is expected to return raw
    results — text fields may still be in whatever casing/format the
    provider's API returned (e.g. ``employment_type="Full-Time"``). The
    scorecard pipeline's own normalize step, not the adapter, is what
    standardizes them; this keeps "how well does this provider's raw data
    normalize" itself a measurable signal.

    ``search`` should raise on a hard failure (unreachable API, invalid
    response shape) — the pipeline records that as a failed scenario
    measurement rather than letting one bad scenario abort a whole
    provider comparison.
    """

    provider_name: str

    def search(self, scenario: SearchScenario) -> list[DiscoveredJob]:
        ...
