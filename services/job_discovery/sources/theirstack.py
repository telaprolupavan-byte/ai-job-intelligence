from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
    normalize_text,
    normalize_url,
)

SEARCH_URL = "https://api.theirstack.com/v1/jobs/search"

# TheirStack's search endpoint rejects a request that specifies none of:
# posted_at_max_age_days / posted_at_gte / posted_at_lte /
# company_domain_or / company_linkedin_url_or / company_name_or. This
# adapter always sends posted_at_max_age_days so a caller never has to
# know a specific company/domain up front (matching Greenhouse, which
# ingests a whole board rather than running a keyword search).
DEFAULT_POSTED_AT_MAX_AGE_DAYS = 7

US_COUNTRY_MARKERS = {"us", "usa", "u.s.", "u.s.a.", "united states"}


class TheirStackAdapterError(RuntimeError):
    """Raised when the TheirStack API cannot be reached or returns an
    unexpected/invalid response. Never includes the API key or any request
    header in its message."""


class TheirStackAuthenticationError(TheirStackAdapterError):
    """Raised on HTTP 401/403 - the API key is missing, invalid, or
    revoked. Never retried: retrying an authentication failure cannot
    succeed and would just burn the caller's retry budget/rate limit."""


class TheirStackRateLimitError(TheirStackAdapterError):
    """Raised on HTTP 429. Retried, bounded by ``max_retries``, with
    exponential backoff."""


class TheirStackTransientError(TheirStackAdapterError):
    """Raised on a network failure, timeout, or HTTP 5xx. Retried, bounded
    by ``max_retries``, with exponential backoff."""


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None

    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _looks_like_us_country(value: str | None) -> bool:
    if not value:
        return False

    return value.strip().lower() in US_COUNTRY_MARKERS


def _first_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value

    return None


def _extract_company_name(raw_job: dict) -> str | None:
    company = raw_job.get("company")

    if isinstance(company, dict):
        name = company.get("name")
        if isinstance(name, str) and name.strip():
            return name
    elif isinstance(company, str) and company.strip():
        return company

    return _first_string(raw_job.get("company_name"))


def _extract_remote_type(raw_job: dict) -> str | None:
    """TheirStack's ``remote`` field has been observed as a boolean flag
    rather than a hybrid/onsite-aware enum. A boolean only tells us
    remote-or-not, never hybrid/onsite - reporting anything more specific
    than that from a bare boolean would be fabricating data the provider
    never sent, so ``False``/absent maps to ``None``, not "onsite"."""
    remote = raw_job.get("remote")

    if isinstance(remote, bool):
        return "remote" if remote else None

    if isinstance(remote, str):
        return remote

    return None


def _extract_employment_type(raw_job: dict) -> str | None:
    statuses = raw_job.get("employment_statuses")

    if isinstance(statuses, list) and statuses:
        first = statuses[0]
        if isinstance(first, str):
            return first

    return _first_string(raw_job.get("employment_type"))


class TheirStackJobSource:
    """
    Fetches job postings from the TheirStack Jobs Search API
    (POST https://api.theirstack.com/v1/jobs/search).

    Unlike Greenhouse's public per-company board API, TheirStack is a
    single authenticated, cross-company search API: ``api_key`` is
    required (a Bearer token), and every request must specify at least
    one TheirStack-required filter - this adapter always sends
    ``posted_at_max_age_days`` so it never needs a specific company
    up front, and additionally lets a caller narrow by job title and
    country code.

    Field-mapping note: TheirStack's exact response field names could not
    be confirmed against a live response while writing this adapter (this
    environment's outbound network access does not reach theirstack.com).
    ``_to_discovered_job`` below is written defensively against the
    publicly documented field names (``data`` as the results list;
    ``job_title``/``title``, ``company.name``/``company_name``,
    ``url``/``final_url``, ``date_posted``, ``remote``,
    ``employment_statuses``) and never fabricates a value for a field it
    can't find - a missing/renamed field simply comes through as ``None``
    (and is then rejected by the existing validator if it was required).
    Confirm the mapping against a real response (see this package's
    README) before relying on TheirStack data quality in production.
    """

    source_name = "theirstack"

    def __init__(
        self,
        *,
        api_key: str,
        job_title_or: list[str] | None = None,
        job_country_code_or: list[str] | None = None,
        posted_at_max_age_days: int = DEFAULT_POSTED_AT_MAX_AGE_DAYS,
        max_results: int = 50,
        page_size: int = 25,
        request_timeout: float = 15.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required.")

        if max_results <= 0:
            raise ValueError("max_results must be a positive integer.")

        if page_size <= 0:
            raise ValueError("page_size must be a positive integer.")

        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")

        self.api_key = api_key
        self.job_title_or = list(job_title_or) if job_title_or else None
        self.job_country_code_or = (
            list(job_country_code_or) if job_country_code_or else ["US"]
        )
        self.posted_at_max_age_days = posted_at_max_age_days
        self.max_results = max_results
        self.page_size = min(page_size, max_results)
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def fetch_jobs(self) -> list[DiscoveredJob]:
        raw_jobs = self._fetch_raw_jobs()

        return [self._to_discovered_job(raw_job) for raw_job in raw_jobs]

    def _fetch_raw_jobs(self) -> list[dict]:
        collected: list[dict] = []
        page = 0

        # Bounded by construction: each iteration either adds a full page
        # (advancing toward max_results) or returns a short page and
        # breaks - never loops more than
        # ceil(max_results / page_size) times.
        while len(collected) < self.max_results:
            remaining = self.max_results - len(collected)
            limit = min(self.page_size, remaining)

            payload = self._post_with_retry(
                self._build_request_body(page=page, limit=limit)
            )

            jobs = payload.get("data")

            if not isinstance(jobs, list):
                raise TheirStackAdapterError(
                    "TheirStack search returned an unexpected response "
                    "shape (missing a 'data' list)."
                )

            collected.extend(jobs)

            if len(jobs) < limit:
                break

            page += 1

        return collected[: self.max_results]

    def _build_request_body(self, *, page: int, limit: int) -> dict:
        body: dict = {
            "page": page,
            "limit": limit,
            "posted_at_max_age_days": self.posted_at_max_age_days,
        }

        if self.job_title_or:
            body["job_title_or"] = self.job_title_or

        if self.job_country_code_or:
            body["job_country_code_or"] = self.job_country_code_or

        return body

    def _post_with_retry(self, body: dict) -> dict:
        attempt = 0
        last_error: TheirStackAdapterError | None = None

        while attempt <= self.max_retries:
            try:
                return self._post(body)
            except (TheirStackRateLimitError, TheirStackTransientError) as exc:
                last_error = exc

                if attempt >= self.max_retries:
                    break

                time.sleep(
                    min(self.retry_backoff_seconds * (2**attempt), 5.0)
                )
                attempt += 1

        assert last_error is not None
        raise last_error

    def _post(self, body: dict) -> dict:
        request = urllib.request.Request(
            SEARCH_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self.request_timeout
            ) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise TheirStackAuthenticationError(
                    f"TheirStack authentication failed (HTTP {exc.code}). "
                    "Check THEIRSTACK_API_KEY."
                ) from exc

            if exc.code == 429:
                raise TheirStackRateLimitError(
                    "TheirStack rate limit exceeded (HTTP 429)."
                ) from exc

            if exc.code >= 500:
                raise TheirStackTransientError(
                    f"TheirStack server error (HTTP {exc.code})."
                ) from exc

            raise TheirStackAdapterError(
                f"TheirStack request failed (HTTP {exc.code})."
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise TheirStackTransientError(
                f"Unable to reach TheirStack: {exc}"
            ) from exc

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise TheirStackAdapterError(
                "TheirStack returned invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise TheirStackAdapterError(
                "TheirStack search returned an unexpected response shape."
            )

        return payload

    def _to_discovered_job(self, raw_job: dict) -> DiscoveredJob:
        title = _first_string(raw_job.get("job_title"), raw_job.get("title"))
        company_name = _extract_company_name(raw_job)

        description = _first_string(
            raw_job.get("description"), raw_job.get("job_description")
        )

        location = _first_string(
            raw_job.get("long_location"),
            raw_job.get("location"),
            raw_job.get("short_location"),
        )

        country = _first_string(
            raw_job.get("country"), raw_job.get("job_country_code")
        )

        application_url = _first_string(
            raw_job.get("url"), raw_job.get("application_url")
        )
        source_url = _first_string(
            raw_job.get("final_url"), raw_job.get("url"), application_url
        )

        job_id = raw_job.get("id")
        if job_id is None:
            job_id = raw_job.get("job_id")

        return DiscoveredJob(
            source=self.source_name,
            source_job_id=str(job_id) if job_id is not None else None,
            title=normalize_text(title) or "",
            company=normalize_text(company_name) or "",
            description=normalize_text(description),
            requirements=None,
            responsibilities=None,
            location=normalize_text(location),
            country="USA" if _looks_like_us_country(country) else "",
            remote_type=normalize_remote_type(_extract_remote_type(raw_job)),
            employment_type=normalize_employment_type(
                _extract_employment_type(raw_job)
            ),
            salary_min=_safe_float(
                raw_job.get("min_annual_salary") or raw_job.get("salary_min")
            ),
            salary_max=_safe_float(
                raw_job.get("max_annual_salary") or raw_job.get("salary_max")
            ),
            salary_currency=normalize_text(raw_job.get("salary_currency")),
            contract_duration=None,
            contract_worker_type=None,
            source_url=normalize_url(source_url),
            application_url=normalize_url(application_url),
            posted_at=_parse_datetime(
                raw_job.get("date_posted") or raw_job.get("posted_at")
            ),
            expires_at=None,
        )
