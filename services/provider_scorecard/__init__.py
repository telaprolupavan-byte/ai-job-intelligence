"""Provider Scorecard Workflow.

A pre-implementation evaluation harness: run the *same* fixed set of
search scenarios against a candidate job-source provider, push the raw
results through the same normalize/deduplicate primitives
``services.job_discovery`` already uses, measure objective quality
metrics, and produce a ``ProviderScorecard`` a Product Owner can compare
across candidate providers before deciding which one (if any) is worth
building a real ``JobSourceAdapter`` for.

See docs/ARCHITECTURE.md ("Provider Scorecard Workflow") for the full
pipeline diagram and scope decisions. This package has no dependency on
apps.api or the database, and makes no AI/LLM calls or network calls of
its own — it only orchestrates whatever ``ProviderSearchAdapter`` the
caller supplies.
"""

from services.provider_scorecard.contracts import (
    ProviderScorecard,
    ScenarioMeasurement,
    SearchScenario,
)

__all__ = [
    "ProviderScorecard",
    "ScenarioMeasurement",
    "SearchScenario",
]
