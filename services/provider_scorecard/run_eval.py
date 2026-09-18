"""
Run the Provider Scorecard workflow against real candidate providers.

NOT part of the production app - a one-off/occasional CLI a developer or
analyst runs when deciding whether a new job-source provider is worth
building a real `services.job_discovery.sources` adapter for. See
services/provider_scorecard/README.md for the full workflow writeup and
each provider's required credentials.

This script was authored (and its adapters written) in a sandboxed
session with no outbound network access to any of the four candidate
hosts (adzuna.com, jooble.org, usajobs.gov, themuse.com were all denied
by the session's egress policy) and with none of their API keys
configured, so it has never actually been executed end-to-end against
live data. Run it somewhere with both network access to those hosts and
the credentials below - do not treat this docstring as a report of
results, because none exist yet.

Usage:
    python -m services.provider_scorecard.run_eval

Required environment variables per provider (a provider without its
variables set is skipped, not failed):

| Provider | Variables |
|---|---|
| Adzuna   | ADZUNA_APP_ID, ADZUNA_APP_KEY (ADZUNA_COUNTRY optional, default "us") |
| Jooble   | JOOBLE_API_KEY |
| USAJOBS  | USAJOBS_API_KEY, USAJOBS_USER_AGENT_EMAIL |
| The Muse | none required (THE_MUSE_API_KEY optional, raises the rate limit) |
"""

from __future__ import annotations

import sys

from services.provider_scorecard.eval_adapters.adzuna import AdzunaEvalAdapter
from services.provider_scorecard.eval_adapters.jooble import JoobleEvalAdapter
from services.provider_scorecard.eval_adapters.the_muse import TheMuseEvalAdapter
from services.provider_scorecard.eval_adapters.usajobs import UsaJobsEvalAdapter
from services.provider_scorecard.pipeline import run_provider_scorecard
from services.provider_scorecard.scenarios import EXAMPLE_SCENARIOS

PROVIDER_BUILDERS = {
    "adzuna": AdzunaEvalAdapter.from_env,
    "jooble": JoobleEvalAdapter.from_env,
    "usajobs": UsaJobsEvalAdapter.from_env,
    "the_muse": TheMuseEvalAdapter.from_env,
}


def main() -> int:
    scorecards = []
    skipped = []

    for name, build in PROVIDER_BUILDERS.items():
        adapter = build()

        if adapter is None:
            skipped.append(name)
            continue

        scorecards.append(run_provider_scorecard(adapter, EXAMPLE_SCENARIOS))

    _print_report(scorecards, skipped)

    return 0


def _print_report(scorecards, skipped) -> None:
    print(f"Scenarios run (see scenarios.py - EXAMPLE_SCENARIOS, not an "
          f"approved canonical set): {[s.scenario_id for s in EXAMPLE_SCENARIOS]}")
    print()

    if skipped:
        print(
            "Skipped (not configured - see this module's docstring for "
            f"required env vars): {', '.join(skipped)}"
        )
        print()

    if not scorecards:
        print("No providers configured - nothing was run.")
        return

    for scorecard in scorecards:
        print(f"== {scorecard.provider} ==")
        print(f"  total fetched:               {scorecard.total_fetched}")
        print(f"  total unique:                {scorecard.total_unique}")
        print(f"  overall duplicate rate:      {scorecard.overall_duplicate_rate:.1%}")
        print(f"  overall validation pass rate:{scorecard.overall_validation_pass_rate:.1%}")
        print(f"  average latency (ms):        {scorecard.average_latency_ms:.0f}")
        print("  average field completeness:")
        for field_name, rate in scorecard.average_field_completeness.items():
            print(f"    {field_name}: {rate:.1%}")

        if scorecard.scenarios_with_errors:
            print(f"  scenarios with errors: {', '.join(scorecard.scenarios_with_errors)}")
            for measurement in scorecard.scenario_measurements:
                if not measurement.succeeded:
                    print(f"    {measurement.scenario_id}: {measurement.error}")

        print()


if __name__ == "__main__":
    sys.exit(main())
