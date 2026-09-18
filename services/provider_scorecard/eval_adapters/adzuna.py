from __future__ import annotations

import os
import urllib.parse
from datetime import datetime

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.contracts import SearchScenario
from services.provider_scorecard.eval_adapters._http import get_json

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class AdzunaEvalAdapter:
    """
    Evaluation-only adapter for the Adzuna Jobs API
    (https://developer.adzuna.com/docs/search), used solely to feed the
    Provider Scorecard workflow - see this package's __init__.py.

    Adzuna requires a free ``app_id``/``app_key`` pair from
    https://developer.adzuna.com/. Country is a path segment on Adzuna's
    own API (one country-scoped endpoint per request), so labeling a
    result "USA" when ``country="us"`` is a hard API constraint, not a
    guess - unlike Greenhouse/Jooble/The Muse, which have no such
    constraint and must infer country from location text instead.

    Known gaps (surfaced by running this, not hidden): Adzuna's
    ``/search`` endpoint has no distinct remote/hybrid/onsite field, and
    does not return a separate salary currency on this endpoint.
    """

    provider_name = "adzuna"

    def __init__(
        self,
        *,
        app_id: str,
        app_key: str,
        country: str = "us",
        results_per_page: int = 20,
        request_timeout: float = 15.0,
    ) -> None:
        if not app_id:
            raise ValueError("app_id is required.")

        if not app_key:
            raise ValueError("app_key is required.")

        self.app_id = app_id
        self.app_key = app_key
        self.country = country
        self.results_per_page = results_per_page
        self.request_timeout = request_timeout

    @classmethod
    def from_env(cls) -> "AdzunaEvalAdapter | None":
        app_id = os.environ.get("ADZUNA_APP_ID")
        app_key = os.environ.get("ADZUNA_APP_KEY")

        if not app_id or not app_key:
            return None

        return cls(
            app_id=app_id,
            app_key=app_key,
            country=os.environ.get("ADZUNA_COUNTRY", "us"),
        )

    def search(self, scenario: SearchScenario) -> list[DiscoveredJob]:
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": str(self.results_per_page),
            "what": scenario.keywords,
            "content-type": "application/json",
        }

        if scenario.location:
            params["where"] = scenario.location

        url = SEARCH_URL.format(country=self.country) + "?" + urllib.parse.urlencode(params)
        payload = get_json(url, timeout=self.request_timeout)

        return self.parse_response(payload, scenario_id=scenario.scenario_id)

    def parse_response(self, payload: dict, *, scenario_id: str = "") -> list[DiscoveredJob]:
        """
        Map an already-fetched raw Adzuna ``/search`` response body into
        ``DiscoveredJob``s. Split out from ``search()`` so a response
        fetched outside this process (e.g. by a developer who has real
        network access and API keys this session doesn't) can still be
        measured by the Provider Scorecard pipeline - see
        ``services/provider_scorecard/ingest.py``.
        """

        results = payload.get("results")

        if not isinstance(results, list):
            raise RuntimeError(
                f"Adzuna returned an unexpected response shape for "
                f"scenario '{scenario_id}'."
            )

        return [self._to_discovered_job(raw) for raw in results]

    def _to_discovered_job(self, raw: dict) -> DiscoveredJob:
        company = (raw.get("company") or {}).get("display_name")
        location = (raw.get("location") or {}).get("display_name")

        return DiscoveredJob(
            source=self.provider_name,
            source_job_id=str(raw["id"]) if raw.get("id") is not None else None,
            title=raw.get("title") or "",
            company=company or "",
            description=raw.get("description"),
            requirements=None,
            responsibilities=None,
            location=location,
            country="USA" if self.country.lower() == "us" else self.country.upper(),
            remote_type=None,
            employment_type=raw.get("contract_time"),
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
            salary_currency=None,
            contract_duration=raw.get("contract_type"),
            contract_worker_type=None,
            source_url=raw.get("redirect_url"),
            application_url=raw.get("redirect_url"),
            posted_at=_parse_datetime(raw.get("created")),
            expires_at=None,
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
