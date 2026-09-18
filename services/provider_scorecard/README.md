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

## Evaluating real candidate providers (Adzuna, Jooble, USAJOBS, The Muse)

`services/provider_scorecard/eval_adapters/` has one `ProviderSearchAdapter`
per candidate, and `run_eval.py` is a ready-to-run CLI:

```
python -m services.provider_scorecard.run_eval
```

These are **evaluation-only** - not `services.job_discovery.sources`
production adapters, not wired into the API/DB/scheduler anywhere. A
provider missing its required env vars is skipped, not failed:

| Provider | Required env vars | Signup needed? |
|---|---|---|
| Adzuna   | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (`ADZUNA_COUNTRY` optional) | Yes - free at developer.adzuna.com |
| Jooble   | `JOOBLE_API_KEY` | Yes - free at jooble.org/api/about |
| USAJOBS  | `USAJOBS_API_KEY`, `USAJOBS_USER_AGENT_EMAIL` | Yes - free at developer.usajobs.gov |
| The Muse | none (`THE_MUSE_API_KEY` optional, raises rate limit) | No |

**Status as of this writing:** these adapters were authored and unit-
tested (against fixture payloads matching each provider's published API
docs) in a sandboxed session whose egress policy denies all four hosts
(`adzuna.com`, `jooble.org`, `usajobs.gov`, `themuse.com`) outright, and
with no credentials configured for the three that require them. They
have therefore never been executed against live data - run `run_eval.py`
somewhere with both network access to those hosts and the credentials
above to get real numbers, and treat that first run's raw output as the
actual verification of the field mappings, not this README.

Each adapter's own docstring documents provider-specific data-quality
gaps discovered just from reading each API's documentation (e.g. The
Muse has no free-text keyword search, Jooble's salary is unstructured
free text, Adzuna has no remote/hybrid/onsite field) - these are exactly
the kind of finding this workflow exists to surface before committing to
build a real adapter for any of them.

## AJI-018C: the live comparison table (Greenhouse included)

The Product Owner-facing deliverable is a table with one column per
provider (Greenhouse + the four candidates) and these rows: Raw jobs,
Valid jobs, Unique jobs, Duplicate %, AI/ML jobs, FT jobs, Contract jobs,
Remote jobs, Salary available, Application URL, Freshness, API
reliability. **No score, rank, or "winner" column** — that decision
belongs to the Product Owner/Planner reading the numbers, never to this
code (see `report.py`'s `ProviderReport` docstring).

This session's egress policy denies all five hosts outright, including
`boards-api.greenhouse.io` — not just the four candidates — so nothing
here can populate that table by calling any of these APIs directly, and
run_eval.py's own live-run attempt (below) proves it rather than just
asserting it. `services/provider_scorecard/ingest.py` exists for exactly
this situation: it builds the same table from raw API responses fetched
by someone who *does* have real access, so the table reflects genuine
measured data instead of either fabricated numbers or an empty template.

```
python -m services.provider_scorecard.ingest path/to/responses.json
```

See `ingest.py`'s module docstring for the exact input file format, and
`response_bundle.example.json` (fabricated data, clearly marked) for a
worked example. In short: fetch each provider's raw response yourself for
each scenario in your shared scenario set (Greenhouse via its normal
board-token URL; Adzuna/Jooble/USAJOBS with your own API keys; The Muse
needs no key), save the response bodies into one JSON file keyed by
provider then scenario ID, and hand that file to `ingest.py`. A request
that failed when you made it (rate limited, timed out, 5xx) can be
recorded as `{"_error": "..."}` instead of a response body — that's what
makes "API reliability" a real measurement rather than always reading
100% because only successes got recorded. A provider you have no access
to is simply left out of the bundle; it will be missing from the table
rather than shown as zeroes (a provider that was never asked is not the
same thing as one that returned nothing).

Every metric in the table is computed the same way `ScenarioMeasurement`
computes its own (reusing the same normalize/deduplicate/validate
primitives - see "What each stage reuses" below), plus:
`report_metrics.py` adds "AI/ML jobs" (a documented keyword heuristic
over title+description, not an authoritative taxonomy), FT/Contract/
Remote counts (compared against the normalizer's own canonical values,
so raw-casing input like `"Full-Time"` still counts correctly),
salary/application-URL availability, and posting freshness (median days
since `posted_at`, `None`/`"N/A"` rather than a fabricated `0` when a
provider discloses no dates at all). Deduplication for this table is
global across every scenario for a given provider, not per scenario - the
same posting surfacing under two different scenario searches counts once
in "Unique jobs," not twice.

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
