"""AJI-028 test double: a synthetic, paged provider built only from the
shared foundation (SourceHttpClient + fetch_bounded_pages), the way a
future approved adapter would be. It is NOT a real source and is never
registered with the application - tests use it to prove the foundation
end to end (fetch -> normalize -> validate -> dedupe -> persist, with
provider-stated expiry) without any network access.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from services.job_discovery.contracts import DiscoveredJob, RawProviderJob
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_text,
    normalize_url,
)
from services.job_discovery.pagination import fetch_bounded_pages
from services.job_discovery.source_http import (
    HttpPolicy,
    HttpResponse,
    SourceHttpClient,
)


EXAMPLE_SOURCE = "example_paged_source"
EXAMPLE_API = "https://api.paged-provider.example/v1/jobs"


def example_record(
    job_id: str,
    *,
    title: str = "Backend Engineer",
    countries: list[str] | None = None,
    expires: int | None = None,
    published: int | None = 1_790_000_000,
) -> dict:
    return {
        "guid": f"https://paged-provider.example/jobs/{job_id}",
        "title": title,
        "companyName": "Example Paged Co (test double)",
        "description": f"{title}: build and run Python services end to end.",
        "employmentType": "Full Time",
        "locationRestrictions": ["United States"] if countries is None else countries,
        "applicationLink": f"https://apply.paged-provider.example/{job_id}",
        "pubDate": published,
        "expiryDate": expires,
    }


class PagedTransport:
    """Serves `records` as pages of `page_size` for ?page=N."""

    def __init__(self, records: list[dict], page_size: int) -> None:
        self.records = records
        self.page_size = page_size
        self.urls: list[str] = []

    def __call__(self, url, headers, timeout_seconds, max_bytes):
        self.urls.append(url)
        page = int(url.rsplit("page=", 1)[1])
        start = (page - 1) * self.page_size
        body = {"jobs": self.records[start:start + self.page_size]}
        return HttpResponse(status=200, headers={}, body=json.dumps(body).encode())


def _from_unix(value) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


class ExamplePagedSource:
    """Synthetic adapter following every AJI-028 contract rule."""

    source_name = EXAMPLE_SOURCE
    is_test_provider = True
    page_size = 2

    def __init__(self, transport, *, max_pages: int = 5) -> None:
        self.client = SourceHttpClient(
            source_name=self.source_name,
            policy=HttpPolicy(min_interval_seconds=0.0),
            transport=transport,
            sleep=lambda seconds: None,
        )
        self.max_pages = max_pages
        self.last_fetch = None

    def _page(self, page_number: int) -> list[dict]:
        payload = self.client.get_json(f"{EXAMPLE_API}?page={page_number}")
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError("unexpected shape")
        return jobs

    def fetch_raw_jobs(self) -> list[RawProviderJob]:
        self.last_fetch = fetch_bounded_pages(
            self._page, page_size=self.page_size, max_pages=self.max_pages
        )
        return [
            RawProviderJob(source=self.source_name, payload=record)
            for record in self.last_fetch.items
            if isinstance(record, dict)
        ]

    def normalize_raw_job(self, raw_job: RawProviderJob) -> DiscoveredJob:
        payload = raw_job.payload
        guid = normalize_url(payload.get("guid"))
        if not guid:
            raise ValueError("record has no guid")

        countries = payload.get("locationRestrictions") or []
        # Explicit U.S. eligibility only; an empty list (worldwide) is not
        # treated as U.S.-eligible (AJI-028 Product Owner decision).
        is_us = "United States" in countries

        return DiscoveredJob(
            source=self.source_name,
            source_job_id=guid,
            title=normalize_text(payload.get("title")) or "",
            company=normalize_text(payload.get("companyName")) or "",
            description=normalize_text(payload.get("description")),
            requirements=None,
            responsibilities=None,
            location=", ".join(countries) or None,
            country="USA" if is_us else "",
            # A confirmed remote-only source may state this (PO decision).
            remote_type="remote",
            employment_type=normalize_employment_type(payload.get("employmentType")),
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            contract_duration=None,
            contract_worker_type=None,
            source_url=guid,
            application_url=normalize_url(payload.get("applicationLink")),
            posted_at=_from_unix(payload.get("pubDate")),
            expires_at=_from_unix(payload.get("expiryDate")),
        )
