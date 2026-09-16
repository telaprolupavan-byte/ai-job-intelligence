from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from datetime import datetime

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
    normalize_text,
)

BOARDS_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

# Greenhouse's public v1 endpoint does not return structured country data.
# We only accept postings whose location text unambiguously reads as U.S.
# rather than guessing, per the "no fabricated country" requirement.
US_LOCATION_MARKERS = {
    "united states",
    "usa",
    "u.s.",
    "u.s.a.",
    " al", " ak", " az", " ar", " ca", " co", " ct", " de", " fl", " ga",
    " hi", " id", " il", " in", " ia", " ks", " ky", " la", " me", " md",
    " ma", " mi", " mn", " ms", " mo", " mt", " ne", " nv", " nh", " nj",
    " nm", " ny", " nc", " nd", " oh", " ok", " or", " pa", " ri", " sc",
    " sd", " tn", " tx", " ut", " vt", " va", " wa", " wv", " wi", " wy",
    " dc",
}

_TAG_PATTERN = re.compile(r"<[^>]+>")


class GreenhouseAdapterError(RuntimeError):
    """Raised when the Greenhouse public board API cannot be read."""


def _looks_like_us_location(location: str | None) -> bool:
    if not location:
        return False

    normalized = f" {location.strip().lower()} "

    return any(marker in normalized for marker in US_LOCATION_MARKERS)


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None

    text = _TAG_PATTERN.sub(" ", value)
    text = html.unescape(text)

    return normalize_text(text)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _find_metadata_value(
    metadata: list[dict] | None,
    *,
    field_names: set[str],
) -> str | None:
    if not metadata:
        return None

    for field in metadata:
        name = str(field.get("name", "")).strip().lower()
        if name in field_names:
            value = field.get("value")
            return str(value) if value is not None else None

    return None


class GreenhouseJobSource:
    """
    Fetches public job postings from a company's Greenhouse job board.

    Greenhouse exposes a public, unauthenticated JSON API for each board:
    https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

    ``board_token`` is the company's Greenhouse board identifier, e.g. for
    https://boards.greenhouse.io/example the token is "example". This is
    configuration, not a credential - no API key is required.
    """

    source_name = "greenhouse"

    def __init__(
        self,
        *,
        board_token: str,
        company_name: str,
        request_timeout: float = 15.0,
    ) -> None:
        if not board_token:
            raise ValueError("board_token is required.")

        if not company_name:
            raise ValueError("company_name is required.")

        self.board_token = board_token
        self.company_name = company_name
        self.request_timeout = request_timeout

    def _fetch_raw_jobs(self) -> list[dict]:
        url = BOARDS_API_URL.format(board_token=self.board_token) + "?content=true"

        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self.request_timeout
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise GreenhouseAdapterError(
                f"Unable to reach Greenhouse board '{self.board_token}': {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise GreenhouseAdapterError(
                f"Greenhouse board '{self.board_token}' returned invalid JSON."
            ) from exc

        jobs = payload.get("jobs")

        if not isinstance(jobs, list):
            raise GreenhouseAdapterError(
                f"Greenhouse board '{self.board_token}' returned an unexpected response shape."
            )

        return jobs

    def fetch_jobs(self) -> list[DiscoveredJob]:
        raw_jobs = self._fetch_raw_jobs()

        return [self._to_discovered_job(raw_job) for raw_job in raw_jobs]

    def _to_discovered_job(self, raw_job: dict) -> DiscoveredJob:
        location = normalize_text(
            (raw_job.get("location") or {}).get("name")
        )

        metadata = raw_job.get("metadata")

        employment_type = normalize_employment_type(
            _find_metadata_value(
                metadata,
                field_names={"employment type", "job type", "work type"},
            )
        )

        remote_type = normalize_remote_type(
            _find_metadata_value(
                metadata,
                field_names={"remote", "workplace type", "work arrangement"},
            )
        )

        return DiscoveredJob(
            source=self.source_name,
            source_job_id=str(raw_job["id"]),
            title=normalize_text(raw_job.get("title")) or "",
            company=self.company_name,
            description=_strip_html(raw_job.get("content")),
            requirements=None,
            responsibilities=None,
            location=location,
            country="USA" if _looks_like_us_location(location) else "",
            remote_type=remote_type,
            employment_type=employment_type,
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            contract_duration=None,
            contract_worker_type=None,
            source_url=raw_job.get("absolute_url"),
            application_url=raw_job.get("absolute_url"),
            posted_at=_parse_datetime(
                raw_job.get("updated_at") or raw_job.get("first_published")
            ),
            expires_at=None,
        )
