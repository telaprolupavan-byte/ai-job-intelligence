from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# AJI-022 owns this `source` value for jobs a user pasted in. No discovery
# provider may ever emit it (the validator rejects it), so a discovered job
# can never be mistaken for, or matched against, a private submission.
RESERVED_USER_SUBMITTED_SOURCE = "user_submitted"


@dataclass(frozen=True)
class RawProviderJob:
    """One record exactly as a provider returned it, before normalization.

    `payload` is the provider's own shape (e.g. one element of Greenhouse's
    `jobs` array). The adapter that fetched it is the only code that knows
    how to read it - see `JobSourceAdapter.normalize_raw_job`.
    """

    source: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveredJob:
    """NERO's canonical, normalized representation of a discovered job -
    the only shape the validator, deduplicator, and persistence layer
    accept. Every field an adapter cannot read from the provider stays
    None (or "" for `country`, which the validator then rejects) - never a
    guessed value."""

    source: str
    source_job_id: str | None
    title: str
    company: str
    description: str | None
    requirements: str | None
    responsibilities: str | None
    location: str | None
    country: str
    remote_type: str | None
    employment_type: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    contract_duration: str | None
    contract_worker_type: str | None
    source_url: str | None
    application_url: str | None
    posted_at: datetime | None
    expires_at: datetime | None
