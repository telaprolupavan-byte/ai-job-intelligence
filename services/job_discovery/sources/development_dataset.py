"""Controlled development job dataset (AJI-030).

This is NOT a real job source and NOT the production provider. It feeds a
fixed set of realistic, entirely synthetic U.S. job records
(`development_dataset.json`, next to this module) through the same
adapter boundary every provider uses, so NERO's job-intelligence workflow
(search, details, job understanding, resume matching, application
tracking) can be developed end to end while no production provider is
approved (AJI-029).

How it differs from `test_fixture.py`: the fixture is a small, deliberately
messy contract fixture whose exact counts tests pin. This dataset is meant
to look like a working job board - varied titles, companies, skills,
experience levels, work arrangements, employment types, salaries, and
posted/closing dates - while still containing one in-batch duplicate and
two invalid records so a run exercises deduplication and validation too.

Dates: the dataset states `posted_days_ago` / `expires_in_days` offsets
(null = no stated expiry; negative = already closed). `fetch_raw_jobs`
resolves them against the start of the current UTC day (or an injected
`now`), so the active/expired mix never goes stale and two runs on the
same day produce identical records. `normalize_raw_job` only reads the
resolved values, so it stays deterministic for a given raw record.

Isolation is the same as the test fixture (see
apps/api/services/job_discovery_service.py and
apps/api/services/job_access.py):
- the orchestration layer only builds this adapter when
  `JOB_DISCOVERY_PROVIDER=development_dataset` AND
  `JOB_DISCOVERY_ENABLE_TEST_PROVIDER=true` are both set;
- every job is stored with `source = DEVELOPMENT_DATASET_SOURCE`, which is
  in `NON_PRODUCTION_SOURCES`: those rows are flagged `is_test_data` in the
  API and hidden from every user-facing query whenever test mode is off.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from services.job_discovery.contracts import DiscoveredJob, RawProviderJob
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
    normalize_text,
)


DEVELOPMENT_DATASET_SOURCE = "nero_development_dataset"

DATASET_PATH = Path(__file__).with_name("development_dataset.json")


def load_dataset_records(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)

    records = document.get("records") if isinstance(document, dict) else None

    if not isinstance(records, list):
        raise ValueError(f"{path.name} has no 'records' list.")

    return records


def _day_start_utc(now: datetime | None) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return datetime.combine(
        now.astimezone(timezone.utc).date(), time.min, tzinfo=timezone.utc
    )


def _offset_iso(anchor: datetime, days: Any, *, sign: int) -> str | None:
    if isinstance(days, bool) or not isinstance(days, int):
        return None

    return (anchor + timedelta(days=sign * days)).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return normalize_text(value) if isinstance(value, str) else None


def _lines(payload: dict[str, Any], key: str) -> str | None:
    """Requirements/responsibilities are stated as lists; store them as
    one trimmed line per item - the shape the rest of NERO already reads."""
    value = payload.get(key)

    if isinstance(value, str):
        value = value.splitlines()

    if not isinstance(value, list):
        return None

    lines = [
        normalize_text(item) for item in value if isinstance(item, str)
    ]
    joined = "\n".join(line for line in lines if line)

    return joined or None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return float(value)


class DevelopmentDatasetJobSource:
    """Offline development-data provider. See the module docstring."""

    source_name = DEVELOPMENT_DATASET_SOURCE
    is_test_provider = True

    def __init__(
        self,
        *,
        now: datetime | None = None,
        records: list[Any] | None = None,
    ) -> None:
        self._now = now
        self._records = records

    def fetch_raw_jobs(self) -> list[RawProviderJob]:
        records = (
            load_dataset_records() if self._records is None else self._records
        )
        anchor = _day_start_utc(self._now)

        raw_jobs = []

        for record in records:
            if not isinstance(record, dict):
                payload = {"__malformed__": record}
            else:
                payload = copy.deepcopy(record)
                payload["posted_at"] = _offset_iso(
                    anchor, payload.pop("posted_days_ago", None), sign=-1
                )
                payload["expires_at"] = _offset_iso(
                    anchor, payload.pop("expires_in_days", None), sign=1
                )

            raw_jobs.append(
                RawProviderJob(source=self.source_name, payload=payload)
            )

        return raw_jobs

    def normalize_raw_job(self, raw_job: RawProviderJob) -> DiscoveredJob:
        payload = raw_job.payload

        if "__malformed__" in payload:
            raise ValueError("Dataset record is not a JSON object.")

        raw_id = _text(payload, "id")
        salary = payload.get("salary")
        salary = salary if isinstance(salary, dict) else {}
        salary_min = _number(salary.get("min"))
        salary_max = _number(salary.get("max"))
        currency = (
            _text(salary, "currency")
            if salary_min is not None or salary_max is not None
            else None
        )

        return DiscoveredJob(
            source=self.source_name,
            source_job_id=raw_id,
            title=_text(payload, "title") or "",
            company=_text(payload, "company") or "",
            description=_text(payload, "description"),
            requirements=_lines(payload, "requirements"),
            responsibilities=_lines(payload, "responsibilities"),
            location=_text(payload, "location"),
            country=_text(payload, "country") or "",
            remote_type=normalize_remote_type(_text(payload, "workplace")),
            employment_type=normalize_employment_type(
                _text(payload, "employment_type")
            ),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency.upper() if currency else None,
            contract_duration=_text(payload, "contract_duration"),
            contract_worker_type=_text(payload, "contract_worker_type"),
            # Deliberately no URLs: there is no real posting to view or
            # apply to, and a link would make the job look live. Identity
            # comes from `id`; application tracking needs no URL.
            source_url=None,
            application_url=None,
            posted_at=_parse_datetime(payload.get("posted_at")),
            # Only the expiry the dataset states (resolved in fetch).
            expires_at=_parse_datetime(payload.get("expires_at")),
        )
