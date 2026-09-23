from __future__ import annotations

import re

from services.job_discovery.contracts import (
    RESERVED_USER_SUBMITTED_SOURCE,
    DiscoveredJob,
)


class JobValidationError(ValueError):
    """Raised when a discovered job does not meet the minimum requirements."""


# A description must carry at least this many letters/digits, and must not
# be a bare placeholder, to count as "meaningful" (AJI-024). Deliberately
# low: this rejects empty/junk records, it is not a quality judgement.
MIN_DESCRIPTION_ALNUM_CHARS = 10

_PLACEHOLDER_DESCRIPTIONS = {
    "n/a",
    "na",
    "none",
    "null",
    "tbd",
    "tba",
    "todo",
    "description",
    "no description",
    "no description provided",
    "see link",
    "see website",
    "see job posting",
    "coming soon",
}

_ALNUM = re.compile(r"[A-Za-z0-9]")

US_COUNTRY_VALUES = {
    "us",
    "usa",
    "united states",
    "united states of america",
}


def is_meaningful_description(value: str | None) -> bool:
    if value is None:
        return False

    text = " ".join(value.split())

    if text.lower().strip(" .!-") in _PLACEHOLDER_DESCRIPTIONS:
        return False

    return len(_ALNUM.findall(text)) >= MIN_DESCRIPTION_ALNUM_CHARS


def validate_discovered_job(job: DiscoveredJob) -> None:
    """Required: title, company, a meaningful description, source, and a
    known U.S. country (the existing product scope). Everything else -
    location, remote/employment type, salary, source/application URL,
    posting date - is optional: a missing value stays unknown and never
    invalidates an otherwise valid job."""
    required_fields = {
        "title": job.title,
        "company": job.company,
        "country": job.country,
        "description": job.description,
        "source": job.source,
    }

    missing_fields = [
        field
        for field, value in required_fields.items()
        if value is None or not str(value).strip()
    ]

    if missing_fields:
        raise JobValidationError(
            f"Missing required fields: {', '.join(missing_fields)}"
        )

    if job.source.strip().lower() == RESERVED_USER_SUBMITTED_SOURCE:
        raise JobValidationError(
            f"Source '{RESERVED_USER_SUBMITTED_SOURCE}' is reserved for "
            "user-submitted jobs and cannot be used by discovery."
        )

    if not is_meaningful_description(job.description):
        raise JobValidationError(
            "Description is not meaningful (placeholder or too short)."
        )

    if job.country.strip().lower() not in US_COUNTRY_VALUES:
        raise JobValidationError(
            "Only United States jobs are currently supported."
        )
