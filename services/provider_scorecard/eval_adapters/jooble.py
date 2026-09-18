from __future__ import annotations

import os
from datetime import datetime

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.contracts import SearchScenario
from services.provider_scorecard.eval_adapters._http import post_json
from services.provider_scorecard.eval_adapters._us_location import looks_like_us_location

SEARCH_URL = "https://jooble.org/api/{api_key}"


class JoobleEvalAdapter:
    """
    Evaluation-only adapter for the Jooble Jobs API
    (https://jooble.org/api/about), used solely to feed the Provider
    Scorecard workflow - see this package's __init__.py.

    Jooble requires a free API key from https://jooble.org/api/about.
    Unlike Adzuna/USAJOBS, Jooble's search is not scoped to one country by
    the API itself, so - like Greenhouse - country is inferred from the
    result's own location text rather than assumed; a job whose location
    text doesn't unambiguously read as U.S. gets ``country=""`` (which the
    scorecard's validation-pass-rate metric will correctly count as
    invalid, rather than silently guessed as "USA").

    Known gap (surfaced by running this, not hidden): Jooble's ``salary``
    field is an unstructured free-text string (e.g. "$80,000 - $100,000"),
    not the numeric min/max ``DiscoveredJob.salary_min``/``salary_max``
    expects - it is dropped here rather than mis-parsed, so a scorecard
    run will show 0% salary-adjacent completeness for this provider even
    though Jooble does return *some* salary text for some postings. A real
    adapter would need its own numeric-range parser for that field.
    """

    provider_name = "jooble"

    def __init__(self, *, api_key: str, request_timeout: float = 15.0) -> None:
        if not api_key:
            raise ValueError("api_key is required.")

        self.api_key = api_key
        self.request_timeout = request_timeout

    @classmethod
    def from_env(cls) -> "JoobleEvalAdapter | None":
        api_key = os.environ.get("JOOBLE_API_KEY")

        if not api_key:
            return None

        return cls(api_key=api_key)

    def search(self, scenario: SearchScenario) -> list[DiscoveredJob]:
        body = {"keywords": scenario.keywords}

        if scenario.location:
            body["location"] = scenario.location

        url = SEARCH_URL.format(api_key=self.api_key)
        payload = post_json(url, body, timeout=self.request_timeout)

        jobs = payload.get("jobs")

        if not isinstance(jobs, list):
            raise RuntimeError(
                f"Jooble returned an unexpected response shape for "
                f"scenario '{scenario.scenario_id}'."
            )

        return [self._to_discovered_job(raw) for raw in jobs]

    def _to_discovered_job(self, raw: dict) -> DiscoveredJob:
        location = raw.get("location")

        return DiscoveredJob(
            source=self.provider_name,
            source_job_id=str(raw["id"]) if raw.get("id") is not None else None,
            title=raw.get("title") or "",
            company=raw.get("company") or "",
            description=raw.get("snippet"),
            requirements=None,
            responsibilities=None,
            location=location,
            country="USA" if looks_like_us_location(location) else "",
            remote_type=None,
            employment_type=raw.get("type"),
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            contract_duration=None,
            contract_worker_type=None,
            source_url=raw.get("link"),
            application_url=raw.get("link"),
            posted_at=_parse_datetime(raw.get("updated")),
            expires_at=None,
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
