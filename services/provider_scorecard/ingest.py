"""
Build the AJI-018C provider comparison table from raw API responses that
were fetched OUTSIDE this session.

Why this exists: this environment's egress policy denies every one of the
five hosts involved (greenhouse.io, adzuna.com, jooble.org, usajobs.gov,
themuse.com - see services/provider_scorecard/run_eval.py's docstring),
so nothing in this repository can call any of these APIs directly. This
module lets someone who *does* have real access (their own machine, a CI
runner with an open policy, etc.) fetch each provider's raw response
themselves and hand the JSON back - it reuses the exact same
normalize/deduplicate/measure logic every other path in this workflow
uses, so the resulting table reflects genuine measured data, never a
fabricated placeholder.

Usage:
    python -m services.provider_scorecard.ingest path/to/responses.json

Expected input file shape (see response_bundle.example.json alongside
this file for a fully worked, clearly-fake example):

{
  "meta": {
    // Required only if a "greenhouse" section is present - Greenhouse's
    // public API response has no company name field of its own.
    "greenhouse_company_name": "Example Inc"
  },
  "greenhouse": {
    "<scenario_id>": <raw JSON body from
        https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true>,
    ...
  },
  "adzuna":  { "<scenario_id>": <raw body from Adzuna's /search endpoint>, ... },
  "jooble":  { "<scenario_id>": <raw body from Jooble's /api/{key} endpoint>, ... },
  "usajobs": { "<scenario_id>": <raw body from USAJOBS' /api/search endpoint>, ... },
  "the_muse": { "<scenario_id>": <raw body from The Muse's /api/public/jobs endpoint>, ... }
}

Every top-level provider key is optional - a bundle only covering
providers you actually have access to still produces a valid (partial)
table; a provider entirely absent from the bundle is left out of the
table rather than shown as zeroes (zero would misleadingly read as "we
tried and got nothing" instead of "we never asked").

A scenario entry may be an error record instead of a raw response, for a
request that was actually attempted and failed - this is what makes "API
reliability" a real, non-fabricated number instead of always reading
100% because only successes were ever recorded:

    "<scenario_id>": {"_error": "HTTP 429 Too Many Requests"}

Never paste a raw request URL or curl command that has your API key
embedded in it (Adzuna/Jooble/USAJOBS all put the key in the URL/path) -
only the response body is needed here.
"""

from __future__ import annotations

import argparse
import json
import sys

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.sources.greenhouse import GreenhouseJobSource
from services.provider_scorecard.eval_adapters.adzuna import AdzunaEvalAdapter
from services.provider_scorecard.eval_adapters.jooble import JoobleEvalAdapter
from services.provider_scorecard.eval_adapters.the_muse import TheMuseEvalAdapter
from services.provider_scorecard.eval_adapters.usajobs import UsaJobsEvalAdapter
from services.provider_scorecard.report import ProviderReport, build_provider_report, render_markdown_table

ERROR_KEY = "_error"


def _parse_greenhouse(payload: dict, *, company_name: str | None) -> list[DiscoveredJob]:
    if not company_name:
        raise ValueError(
            "bundle['meta']['greenhouse_company_name'] is required when a "
            "'greenhouse' entry is present - Greenhouse's own response has "
            "no company name field."
        )

    jobs = payload.get("jobs")

    if not isinstance(jobs, list):
        raise RuntimeError("Greenhouse bundle entry is missing a 'jobs' list.")

    # board_token is unused for parsing an already-fetched response (it
    # only matters for building the fetch URL, which this path never
    # does) - "ingested" is a harmless placeholder, not a real token.
    source = GreenhouseJobSource(board_token="ingested", company_name=company_name)

    return [source._to_discovered_job(job) for job in jobs]


def _parse_adzuna(payload: dict, **_ignored) -> list[DiscoveredJob]:
    return AdzunaEvalAdapter(app_id="ingested", app_key="ingested").parse_response(payload)


def _parse_jooble(payload: dict, **_ignored) -> list[DiscoveredJob]:
    return JoobleEvalAdapter(api_key="ingested").parse_response(payload)


def _parse_usajobs(payload: dict, **_ignored) -> list[DiscoveredJob]:
    return UsaJobsEvalAdapter(
        api_key="ingested", user_agent_email="ingested@example.com"
    ).parse_response(payload)


def _parse_the_muse(payload: dict, **_ignored) -> list[DiscoveredJob]:
    return TheMuseEvalAdapter().parse_response(payload)


PROVIDER_PARSERS = {
    "greenhouse": _parse_greenhouse,
    "adzuna": _parse_adzuna,
    "jooble": _parse_jooble,
    "usajobs": _parse_usajobs,
    "the_muse": _parse_the_muse,
}


def build_reports_from_bundle(bundle: dict) -> list[ProviderReport]:
    meta = bundle.get("meta") or {}
    reports = []

    for provider_key, parse in PROVIDER_PARSERS.items():
        scenarios = bundle.get(provider_key)

        if not scenarios:
            continue

        raw_jobs_by_scenario: dict[str, list[DiscoveredJob]] = {}
        errors_by_scenario: dict[str, str] = {}

        for scenario_id, entry in scenarios.items():
            if isinstance(entry, dict) and ERROR_KEY in entry:
                errors_by_scenario[scenario_id] = str(entry[ERROR_KEY])
                continue

            raw_jobs_by_scenario[scenario_id] = parse(
                entry, company_name=meta.get("greenhouse_company_name")
            )

        reports.append(
            build_provider_report(
                provider_key,
                raw_jobs_by_scenario,
                errors_by_scenario=errors_by_scenario,
            )
        )

    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_path", help="Path to a responses JSON file (see module docstring).")
    args = parser.parse_args(argv)

    with open(args.bundle_path, encoding="utf-8") as handle:
        bundle = json.load(handle)

    reports = build_reports_from_bundle(bundle)

    if not reports:
        print("No provider entries found in the bundle - nothing to report.")
        return 1

    print(render_markdown_table(reports))

    return 0


if __name__ == "__main__":
    sys.exit(main())
