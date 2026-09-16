from __future__ import annotations

from services.job_discovery.contracts import DiscoveredJob


class JobValidationError(ValueError):
    """Raised when a discovered job does not meet the minimum requirements."""


def validate_discovered_job(job: DiscoveredJob) -> None:
    required_fields = {
        "title": job.title,
        "company": job.company,
        "country": job.country,
        "description": job.description,
        "source": job.source,
        "source_url": job.source_url,
        "application_url": job.application_url,
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

    if job.country.strip().lower() not in {
        "us",
        "usa",
        "united states",
        "united states of america",
    }:
        raise JobValidationError(
            "Only United States jobs are currently supported."
        )