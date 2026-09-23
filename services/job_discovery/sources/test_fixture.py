"""Deterministic fixture provider for tests and local development (AJI-024).

This is NOT a real job source. Every record below is synthetic, every
company name says so, and every URL uses the reserved `.example` TLD
(RFC 2606), so nothing here can be mistaken for, or resolve to, a real
posting. It exists so the full discovery product pipeline can be exercised
end to end before a real provider is approved and configured.

Isolation (see apps/api/services/job_discovery_service.py and
apps/api/services/job_access.py):
- the orchestration layer only builds this adapter when
  `JOB_DISCOVERY_PROVIDER=test_fixture` AND
  `JOB_DISCOVERY_ENABLE_TEST_PROVIDER=true` are both set;
- every job it produces is stored with `source = TEST_FIXTURE_SOURCE`, and
  those rows are hidden from every user-facing query whenever test mode is
  off, so fixture data can never surface as production data.

The raw records deliberately use messy, provider-style shapes (mixed-case
employment types, extra whitespace, an unsafe URL, missing fields) so that
running them exercises normalization, validation, and deduplication - they
are raw provider input, not pre-normalized DiscoveredJob objects.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from services.job_discovery.contracts import DiscoveredJob, RawProviderJob
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
    normalize_text,
    normalize_url,
)


TEST_FIXTURE_SOURCE = "nero_test_fixture"

_FIXTURE_COMPANY = "Fixture Labs (NERO test data)"
_FIXTURE_BASE_URL = "https://jobs.nero-fixture.example/postings"


def _url(job_id: str) -> str:
    return f"{_FIXTURE_BASE_URL}/{job_id}"


# Order is part of the contract: tests assert the exact counts this batch
# produces. Expected outcome per record is noted inline.
_RAW_RECORDS: list[Any] = [
    # 1. Full-time, hybrid, fully populated -> inserted.
    {
        "id": "fx-1001",
        "title": "  Senior Backend Engineer  ",
        "company": _FIXTURE_COMPANY,
        "description": (
            "Design and operate Python services that power a job search "
            "product. You will own APIs end to end."
        ),
        "requirements": "5+ years of Python.\nExperience with PostgreSQL.",
        "responsibilities": "Build APIs.\nReview code.",
        "employment_type": "Full-Time",
        "workplace": "Hybrid",
        "location": "Austin, TX",
        "country": "USA",
        "url": _url("fx-1001"),
        "apply_url": _url("fx-1001") + "/apply",
        "posted_at": "2026-09-01T09:00:00Z",
    },
    # 2. Contract, remote, contract details, no posting date -> inserted.
    {
        "id": "fx-1002",
        "title": "Data Pipeline Contractor",
        "company": _FIXTURE_COMPANY,
        "description": (
            "Six-month engagement building batch data pipelines in SQL "
            "and Python for an analytics team."
        ),
        "requirements": "Strong SQL.\nAirflow or a similar orchestrator.",
        "responsibilities": None,
        "employment_type": "contractor",
        "workplace": "Fully Remote",
        "location": "Remote, United States",
        "country": "United States",
        "contract_duration": "6 months",
        "contract_worker_type": "w2",
        "url": _url("fx-1002"),
        "apply_url": None,
        "posted_at": None,
    },
    # 3. Exact repeat of record 1 in the same batch -> duplicate.
    {
        "id": "fx-1001",
        "title": "Senior Backend Engineer",
        "company": _FIXTURE_COMPANY,
        "description": (
            "Design and operate Python services that power a job search "
            "product. You will own APIs end to end."
        ),
        "requirements": "5+ years of Python.\nExperience with PostgreSQL.",
        "responsibilities": "Build APIs.\nReview code.",
        "employment_type": "Full-Time",
        "workplace": "Hybrid",
        "location": "Austin, TX",
        "country": "USA",
        "url": _url("fx-1001"),
        "apply_url": _url("fx-1001") + "/apply",
        "posted_at": "2026-09-01T09:00:00Z",
    },
    # 4. Onsite, unrecognized employment type (stays unknown), no salary,
    #    unsafe apply URL (dropped) -> inserted with those fields None.
    {
        "id": "fx-1003",
        "title": "Frontend Engineer",
        "company": _FIXTURE_COMPANY,
        "description": (
            "Build accessible React interfaces for a data-heavy product "
            "used by job seekers every day."
        ),
        "requirements": None,
        "responsibilities": None,
        "employment_type": "Gig",
        "workplace": "On-site",
        "location": "New York, NY",
        "country": "USA",
        "url": _url("fx-1003"),
        "apply_url": "javascript:alert(1)",
        "posted_at": "2026-08-20T00:00:00",
    },
    # 5. No stable provider id, no location/remote/employment info ->
    #    inserted via the fallback fingerprint; unknowns stay None.
    {
        "id": None,
        "title": "QA Automation Engineer",
        "company": _FIXTURE_COMPANY,
        "description": (
            "Write and maintain automated end-to-end tests for web and "
            "API surfaces."
        ),
        "country": "USA",
        "url": None,
        "apply_url": None,
    },
    # 6. Missing title -> rejected by validation.
    {
        "id": "fx-bad-1",
        "title": "   ",
        "company": _FIXTURE_COMPANY,
        "description": "A posting that is missing its title entirely here.",
        "country": "USA",
    },
    # 7. Placeholder description -> rejected by validation.
    {
        "id": "fx-bad-2",
        "title": "Mystery Role",
        "company": _FIXTURE_COMPANY,
        "description": "TBD",
        "country": "USA",
    },
    # 8. Non-U.S. location -> rejected (existing U.S.-only scope).
    {
        "id": "fx-1004",
        "title": "Site Reliability Engineer",
        "company": _FIXTURE_COMPANY,
        "description": (
            "Keep a distributed platform reliable and observable across "
            "multiple regions."
        ),
        "employment_type": "Full Time",
        "workplace": "Onsite",
        "location": "Berlin, Germany",
        "country": "Germany",
        "url": _url("fx-1004"),
    },
    # 9. Structurally malformed record (not an object) -> rejected by
    #    normalization, without failing the run.
    "this record is not a job object",
]


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return normalize_text(value) if isinstance(value, str) else None


def _multiline_text(payload: dict[str, Any], key: str) -> str | None:
    """Keep line structure (requirements/responsibilities are line lists)
    while trimming each line - the same shape AJI-022 stores."""
    value = payload.get(key)

    if not isinstance(value, str):
        return None

    lines = [normalize_text(line) for line in value.splitlines()]
    joined = "\n".join(line for line in lines if line)

    return joined or None


class TestFixtureJobSource:
    """Deterministic, offline fixture provider. See the module docstring."""

    # Not a pytest test class, despite the name.
    __test__ = False

    source_name = TEST_FIXTURE_SOURCE
    is_test_provider = True

    def fetch_raw_jobs(self) -> list[RawProviderJob]:
        return [
            RawProviderJob(
                source=self.source_name,
                payload=(
                    copy.deepcopy(record)
                    if isinstance(record, dict)
                    else {"__malformed__": record}
                ),
            )
            for record in _RAW_RECORDS
        ]

    def normalize_raw_job(self, raw_job: RawProviderJob) -> DiscoveredJob:
        payload = raw_job.payload

        if "__malformed__" in payload:
            raise ValueError("Fixture record is not a JSON object.")

        raw_id = payload.get("id")

        return DiscoveredJob(
            source=self.source_name,
            source_job_id=str(raw_id) if raw_id not in (None, "") else None,
            title=_text(payload, "title") or "",
            company=_text(payload, "company") or "",
            description=_text(payload, "description"),
            requirements=_multiline_text(payload, "requirements"),
            responsibilities=_multiline_text(payload, "responsibilities"),
            location=_text(payload, "location"),
            country=_text(payload, "country") or "",
            remote_type=normalize_remote_type(_text(payload, "workplace")),
            employment_type=normalize_employment_type(
                _text(payload, "employment_type")
            ),
            # The fixture never states compensation; unknown stays unknown.
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            contract_duration=_text(payload, "contract_duration"),
            contract_worker_type=_text(payload, "contract_worker_type"),
            source_url=normalize_url(_text(payload, "url")),
            application_url=normalize_url(_text(payload, "apply_url")),
            posted_at=_parse_datetime(payload.get("posted_at")),
            expires_at=None,
        )
