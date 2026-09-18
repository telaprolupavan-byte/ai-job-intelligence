from __future__ import annotations

import os
import urllib.parse
from datetime import datetime

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.contracts import SearchScenario
from services.provider_scorecard.eval_adapters._http import get_json
from services.provider_scorecard.eval_adapters._us_location import looks_like_us_location

SEARCH_URL = "https://www.themuse.com/api/public/jobs"


class TheMuseEvalAdapter:
    """
    Evaluation-only adapter for The Muse's public Jobs API
    (https://www.themuse.com/developers/api/v2), used solely to feed the
    Provider Scorecard workflow - see this package's __init__.py.

    The Muse's public jobs endpoint needs no API key for basic use (an
    optional ``api_key`` only raises the rate limit), so
    ``from_env()`` always returns a configured adapter - the one candidate
    of the four with no signup requirement at all.

    Known gap (surfaced by running this, not hidden, not silently mapped
    around): the public endpoint has no free-text keyword search
    parameter - only ``category``/``location``/``level``/``company``
    filters. ``scenario.keywords`` is therefore NOT sent to The Muse at
    all (there is no field to map it onto without guessing a
    keyword-to-category mapping nobody has approved); only
    ``scenario.location`` is applied. This means The Muse's measured
    result set answers "everything in this location" rather than "this
    scenario's actual search," which is itself exactly the kind of
    provider-capability gap this workflow exists to surface before anyone
    commits to building a real adapter for it.
    """

    provider_name = "the_muse"

    def __init__(self, *, api_key: str | None = None, request_timeout: float = 15.0) -> None:
        self.api_key = api_key
        self.request_timeout = request_timeout

    @classmethod
    def from_env(cls) -> "TheMuseEvalAdapter":
        return cls(api_key=os.environ.get("THE_MUSE_API_KEY"))

    def search(self, scenario: SearchScenario) -> list[DiscoveredJob]:
        params = {"page": "1"}

        if scenario.location:
            params["location"] = scenario.location

        if self.api_key:
            params["api_key"] = self.api_key

        url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
        payload = get_json(url, timeout=self.request_timeout)

        results = payload.get("results")

        if not isinstance(results, list):
            raise RuntimeError(
                f"The Muse returned an unexpected response shape for "
                f"scenario '{scenario.scenario_id}'."
            )

        return [self._to_discovered_job(raw) for raw in results]

    def _to_discovered_job(self, raw: dict) -> DiscoveredJob:
        company = (raw.get("company") or {}).get("name")

        location_names = [
            loc.get("name") for loc in (raw.get("locations") or []) if loc.get("name")
        ]
        location = "; ".join(location_names) if location_names else None

        remote_type = None
        if any("remote" in name.lower() for name in location_names):
            remote_type = "Remote"

        refs = raw.get("refs") or {}

        return DiscoveredJob(
            source=self.provider_name,
            source_job_id=str(raw["id"]) if raw.get("id") is not None else None,
            title=raw.get("name") or "",
            company=company or "",
            # Raw HTML, deliberately not stripped - see this module's
            # docstring "Known gap" note; a real adapter would need its own
            # HTML-stripping step, the same way Greenhouse's does.
            description=raw.get("contents"),
            requirements=None,
            responsibilities=None,
            location=location,
            country="USA" if looks_like_us_location(location) else "",
            remote_type=remote_type,
            employment_type=None,
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            contract_duration=None,
            contract_worker_type=None,
            source_url=refs.get("landing_page"),
            application_url=refs.get("landing_page"),
            posted_at=_parse_datetime(raw.get("publication_date")),
            expires_at=None,
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
