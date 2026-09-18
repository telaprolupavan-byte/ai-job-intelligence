# Provider Scorecard Workflow

```
Provider
   |
Same NERO search scenarios
   |
Raw results
   |
Normalize
   |
Deduplicate
   |
Measure
   |
Provider Scorecard
   |
Product Owner decision
   |
Implementation
```

A pre-implementation evaluation harness for candidate job-source
providers (e.g. a new job search API being considered alongside the
existing Greenhouse adapter — see `services/job_discovery/`). It answers
one question: *given the exact same set of search scenarios, how does
this provider's raw data compare to another's once it goes through the
same normalize/deduplicate steps real discovery would apply?*

It never touches the database and never decides anything on its own —
the output (`ProviderScorecard`) is descriptive metrics only. Whether a
provider is worth building a real `JobSourceAdapter` for
("Implementation") is a Product Owner call, made by comparing scorecards
across candidates.

## Running a comparison

```python
from services.provider_scorecard.pipeline import compare_providers
from services.provider_scorecard.scenarios import EXAMPLE_SCENARIOS

# Each adapter implements ProviderSearchAdapter
# (services/provider_scorecard/adapter.py): provider_name + a
# search(scenario) -> list[DiscoveredJob] method. It's fine (expected,
# even) for the returned jobs to still have raw/un-normalized text - the
# pipeline's own normalize step measures how cleanly that data
# standardizes, the same way production discovery would.
scorecards = compare_providers(
    [candidate_a_adapter, candidate_b_adapter],
    EXAMPLE_SCENARIOS,
)

for scorecard in scorecards:
    print(scorecard.provider, scorecard.overall_validation_pass_rate)
```

## The scenario set is a product decision, not a Builder default

`services/provider_scorecard/scenarios.py::EXAMPLE_SCENARIOS` exists so
the pipeline is runnable and testable before a real scenario list
exists — it is explicitly **not** an approved canonical set. Which
searches represent NERO's real target users (titles, locations, remote
preferences) is the same kind of product/legal call the Job Discovery
config deliberately leaves unset by default (see
`services/job_discovery/README.md`'s "no hardcoded board token"
rationale). Whoever runs a real provider comparison should supply the
Product-Owner-approved `list[SearchScenario]` instead of the example set.

Whatever list is used, the fairness of the comparison depends on every
candidate provider being run against the *identical* list — that's what
"Same NERO search scenarios" in the diagram means, and it's why
`compare_providers()` takes one `scenarios` argument shared across every
adapter rather than letting each adapter supply its own.

## What each stage reuses (not reimplements)

- **Normalize** — `services/provider_scorecard/normalize.py` applies
  `services.job_discovery.normalizer`'s existing field-level rules
  (`normalize_text`, `normalize_employment_type`, `normalize_remote_type`,
  `normalize_url`) verbatim, so "does this provider's data normalize
  cleanly" measures the same rules production discovery would apply, not
  a parallel set of eval-only rules.
- **Deduplicate** — `services.job_discovery.deduplicator.build_job_fingerprint`
  is reused unchanged to count unique vs. duplicate postings per scenario.
- **Measure** — `validate_discovered_job` (`services.job_discovery.validator`)
  is reused to compute a validation pass rate, but unlike the real
  discovery pipeline an invalid job is never dropped here — the point of
  this stage is to *count* how often a provider's data would fail
  validation, not to filter a result set nobody is persisting.

## What a `ScenarioMeasurement` records

Per (provider, scenario): fetched/unique/duplicate counts and rate,
valid/invalid counts and validation pass rate, per-field completeness
(title, company, description, location, remote/employment type, source
and application URLs, posted date — salary is deliberately excluded, see
`metrics.py`'s docstring), fetch latency, and — if the adapter raised —
the error, with every other metric left at its zero default rather than
guessed. A failed scenario is excluded from a `ProviderScorecard`'s
weighted-average aggregates (`overall_duplicate_rate`,
`overall_validation_pass_rate`, `average_latency_ms`,
`average_field_completeness`) rather than silently counted as a zero,
which would understate a provider that failed on only one scenario out of
many.

## Why no DB persistence, no HTTP endpoint (a documented scope decision)

This is a one-off (or occasional, re-run-when-evaluating-a-new-candidate)
decision-support tool, not a production data path — nothing here is
meant to run on a schedule or be queried by the frontend. That's a
deliberate contrast with Job Discovery's own operationalization (see
`services/job_discovery/README.md`'s "Operationalizing discovery"
section): discovery ingests jobs a user will actually see, so it needed a
persisted, schedulable, observable path. A provider comparison run by
whoever is deciding *whether* to build a new adapter has no such
requirement, and adding one (a table, an endpoint, auth) would be
infrastructure this workflow doesn't need yet. If a future need emerges
to track scorecards over time or expose them to non-engineers, that is
its own ticket - not an extension bolted onto this one.
