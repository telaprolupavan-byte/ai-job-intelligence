from __future__ import annotations

import os
import urllib.parse
from datetime import datetime

from services.job_discovery.contracts import DiscoveredJob
from services.provider_scorecard.contracts import SearchScenario
from services.provider_scorecard.eval_adapters._http import get_json

SEARCH_URL = "https://data.usajobs.gov/api/search"


class UsaJobsEvalAdapter:
    """
    Evaluation-only adapter for the USAJOBS Search API
    (https://developer.usajobs.gov/), used solely to feed the Provider
    Scorecard workflow - see this package's __init__.py.

    USAJOBS requires a free API key from
    https://developer.usajobs.gov/apirequest/ plus a contact email sent
    as the ``User-Agent`` header (their documented auth convention - not
    an arbitrary choice made here). Every result is a U.S. federal
    posting, so ``country="USA"`` is a hard property of the API itself,
    not inferred from location text.

    Known gap (surfaced by running this, not hidden): USAJOBS has no
    single clean "is this remote" field - ``remote_type`` is left ``None``
    rather than guessed from ``PositionLocationDisplay`` text (a real
    adapter would need to decide how much of that ambiguity to resolve).
    """

    provider_name = "usajobs"

    def __init__(
        self,
        *,
        api_key: str,
        user_agent_email: str,
        results_per_page: int = 25,
        request_timeout: float = 15.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required.")

        if not user_agent_email:
            raise ValueError("user_agent_email is required.")

        self.api_key = api_key
        self.user_agent_email = user_agent_email
        self.results_per_page = results_per_page
        self.request_timeout = request_timeout

    @classmethod
    def from_env(cls) -> "UsaJobsEvalAdapter | None":
        api_key = os.environ.get("USAJOBS_API_KEY")
        user_agent_email = os.environ.get("USAJOBS_USER_AGENT_EMAIL")

        if not api_key or not user_agent_email:
            return None

        return cls(api_key=api_key, user_agent_email=user_agent_email)

    def search(self, scenario: SearchScenario) -> list[DiscoveredJob]:
        params = {
            "Keyword": scenario.keywords,
            "ResultsPerPage": str(self.results_per_page),
        }

        if scenario.location:
            params["LocationName"] = scenario.location

        url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": self.user_agent_email,
            "Authorization-Key": self.api_key,
            "Accept": "application/json",
        }

        payload = get_json(url, headers=headers, timeout=self.request_timeout)

        return self.parse_response(payload, scenario_id=scenario.scenario_id)

    def parse_response(self, payload: dict, *, scenario_id: str = "") -> list[DiscoveredJob]:
        """See AdzunaEvalAdapter.parse_response's docstring - same purpose."""

        search_result = payload.get("SearchResult") or {}
        items = search_result.get("SearchResultItems")

        if not isinstance(items, list):
            raise RuntimeError(
                f"USAJOBS returned an unexpected response shape for "
                f"scenario '{scenario_id}'."
            )

        return [self._to_discovered_job(item) for item in items]

    def _to_discovered_job(self, item: dict) -> DiscoveredJob:
        descriptor = item.get("MatchedObjectDescriptor") or {}

        job_summary = (
            (descriptor.get("UserArea") or {})
            .get("Details", {})
            .get("JobSummary")
        )

        remuneration = descriptor.get("PositionRemuneration") or [{}]
        salary_min, salary_max = _parse_remuneration(remuneration[0] if remuneration else {})

        schedule = descriptor.get("PositionSchedule") or [{}]
        employment_type = (schedule[0] or {}).get("Name") if schedule else None

        apply_uris = descriptor.get("ApplyURI") or []

        return DiscoveredJob(
            source=self.provider_name,
            source_job_id=str(item.get("MatchedObjectId"))
            if item.get("MatchedObjectId") is not None
            else None,
            title=descriptor.get("PositionTitle") or "",
            company=descriptor.get("OrganizationName") or "",
            description=job_summary,
            requirements=None,
            responsibilities=None,
            location=descriptor.get("PositionLocationDisplay"),
            country="USA",
            remote_type=None,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD" if salary_min is not None or salary_max is not None else None,
            contract_duration=None,
            contract_worker_type=None,
            source_url=descriptor.get("PositionURI"),
            application_url=apply_uris[0] if apply_uris else descriptor.get("PositionURI"),
            posted_at=_parse_date(descriptor.get("PublicationStartDate")),
            expires_at=_parse_date(descriptor.get("ApplicationCloseDate")),
        )


def _parse_remuneration(remuneration: dict) -> tuple[float | None, float | None]:
    def _to_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return _to_float(remuneration.get("MinimumRange")), _to_float(remuneration.get("MaximumRange"))


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
