from dataclasses import dataclass
from datetime import datetime


@dataclass
class DiscoveredJob:
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