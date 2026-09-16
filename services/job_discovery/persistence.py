from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models import Company, Job
from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.deduplicator import build_job_fingerprint
from services.job_discovery.normalizer import normalize_text
from services.job_discovery.validator import validate_discovered_job


def normalize_company_name(name: str) -> str:
    return " ".join(name.lower().split())


def get_or_create_company(
    db: Session,
    discovered_job: DiscoveredJob,
) -> Company:
    normalized_name = normalize_company_name(discovered_job.company)

    company = db.scalar(
        select(Company).where(
            Company.normalized_name == normalized_name
        )
    )

    if company:
        return company

    company = Company(
        name=normalize_text(discovered_job.company),
        normalized_name=normalized_name,
    )

    db.add(company)
    db.flush()

    return company


def upsert_discovered_job(
    db: Session,
    discovered_job: DiscoveredJob,
) -> Job:
    validate_discovered_job(discovered_job)

    company = get_or_create_company(db, discovered_job)
    fingerprint = build_job_fingerprint(discovered_job)

    existing_job = None

    if discovered_job.source_job_id:
        existing_job = db.scalar(
            select(Job).where(
                Job.source == discovered_job.source,
                Job.external_job_id == discovered_job.source_job_id,
            )
        )
    else:
        # No stable source job ID: fall back to the identity fingerprint
        # so repeated ingestion of the same posting updates it in place.
        existing_job = db.scalar(
            select(Job).where(
                Job.source == discovered_job.source,
                Job.identity_fingerprint == fingerprint,
            )
        )

    if existing_job is None:
        now = datetime.now(timezone.utc)

        job = Job(
            company_id=company.id,
            title=discovered_job.title,
            location=discovered_job.location,
            country=discovered_job.country,
            remote_type=discovered_job.remote_type,
            employment_type=discovered_job.employment_type,
            salary_min=discovered_job.salary_min,
            salary_max=discovered_job.salary_max,
            salary_currency=discovered_job.salary_currency,
            contract_duration=discovered_job.contract_duration,
            contract_worker_type=discovered_job.contract_worker_type,
            description=discovered_job.description,
            requirements=discovered_job.requirements,
            responsibilities=discovered_job.responsibilities,
            posting_date=discovered_job.posted_at,
            source=discovered_job.source,
            source_url=discovered_job.source_url,
            application_url=discovered_job.application_url,
            external_job_id=discovered_job.source_job_id,
            identity_fingerprint=fingerprint,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
        )

        db.add(job)
        db.flush()

        return job

    existing_job.company_id = company.id
    existing_job.title = discovered_job.title
    existing_job.location = discovered_job.location
    existing_job.country = discovered_job.country
    existing_job.remote_type = discovered_job.remote_type
    existing_job.employment_type = discovered_job.employment_type
    existing_job.salary_min = discovered_job.salary_min
    existing_job.salary_max = discovered_job.salary_max
    existing_job.salary_currency = discovered_job.salary_currency
    existing_job.contract_duration = discovered_job.contract_duration
    existing_job.contract_worker_type = discovered_job.contract_worker_type
    existing_job.description = discovered_job.description
    existing_job.requirements = discovered_job.requirements
    existing_job.responsibilities = discovered_job.responsibilities
    existing_job.posting_date = discovered_job.posted_at
    existing_job.source_url = discovered_job.source_url
    existing_job.application_url = discovered_job.application_url
    existing_job.identity_fingerprint = fingerprint
    existing_job.last_seen_at = datetime.now(timezone.utc)
    existing_job.is_active = True

    db.flush()

    return existing_job