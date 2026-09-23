from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models import Company, Job
from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.deduplicator import build_job_fingerprint
from services.job_discovery.normalizer import normalize_text
from services.job_discovery.validator import validate_discovered_job


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Coerce a datetime to naive UTC for the `jobs` timestamp columns.

    `jobs.posting_date`/`first_seen_at`/`last_seen_at` are
    `TIMESTAMP WITHOUT TIME ZONE` columns that hold UTC by convention
    (their model defaults are naive `datetime.utcnow`). Binding an
    *aware* datetime to one of them makes Postgres cast timestamptz ->
    timestamp using the server session's `TimeZone`, so the value is
    silently shifted by that offset on any deployment whose Postgres
    session timezone is not UTC - which then skews `first_seen_at`
    ordering and the dashboard's "jobs today" date bucket.

    Discovery feeds both kinds: `datetime.now(timezone.utc)` is aware,
    and a source's ISO-8601 `posted_at` (e.g. Greenhouse's "...Z") parses
    aware too, while a source without an offset parses naive. Converting
    here - the single boundary where discovered data enters the DB -
    keeps what is stored identical regardless of the server's timezone.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utcnow_naive() -> datetime:
    """Current UTC time in the naive form the `jobs` columns expect."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def find_existing_discovered_job(
    db: Session,
    discovered_job: DiscoveredJob,
    *,
    fingerprint: str,
) -> Job | None:
    """The stored discovered job this record is the same posting as, if
    any. Identity is (source, source job id) when the provider supplies
    one, else (source, identity fingerprint) - the AJI-006 rules, unchanged.

    Only shared discovered rows (`submitted_by_user_id IS NULL`) are ever
    candidates: discovery must never update a user's private submission
    (AJI-022), whatever its source or fingerprint happens to be.
    """
    query = select(Job).where(
        Job.source == discovered_job.source,
        Job.submitted_by_user_id.is_(None),
    )

    if discovered_job.source_job_id:
        query = query.where(
            Job.external_job_id == discovered_job.source_job_id
        )
    else:
        # No stable source job ID: fall back to the identity fingerprint
        # so repeated ingestion of the same posting updates it in place.
        query = query.where(Job.identity_fingerprint == fingerprint)

    return db.scalar(query)


def upsert_discovered_job(
    db: Session,
    discovered_job: DiscoveredJob,
) -> Job:
    validate_discovered_job(discovered_job)

    company = get_or_create_company(db, discovered_job)
    fingerprint = build_job_fingerprint(discovered_job)

    existing_job = find_existing_discovered_job(
        db, discovered_job, fingerprint=fingerprint
    )

    if existing_job is None:
        now = utcnow_naive()

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
            posting_date=to_naive_utc(discovered_job.posted_at),
            source=discovered_job.source,
            source_url=discovered_job.source_url,
            application_url=discovered_job.application_url,
            external_job_id=discovered_job.source_job_id,
            identity_fingerprint=fingerprint,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
            # Discovered jobs are shared (AJI-022): never owned by a user
            # and never carrying pasted content.
            submitted_by_user_id=None,
            raw_submitted_content=None,
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
    existing_job.posting_date = to_naive_utc(discovered_job.posted_at)
    existing_job.source_url = discovered_job.source_url
    existing_job.application_url = discovered_job.application_url
    existing_job.identity_fingerprint = fingerprint
    existing_job.last_seen_at = utcnow_naive()
    existing_job.is_active = True

    db.flush()

    return existing_job