from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.persistence import upsert_discovered_job
from apps.api.models import Company, Job


def make_job(**overrides) -> DiscoveredJob:
    values = {
        "source": "greenhouse",
        "source_job_id": "persistence-test-123",
        "title": "Machine Learning Engineer",
        "company": "Persistence Test AI",
        "description": "Build machine learning systems.",
        "requirements": "Python, PyTorch",
        "responsibilities": "Develop ML systems.",
        "location": "New York, NY",
        "country": "USA",
        "remote_type": "hybrid",
        "employment_type": "full_time",
        "salary_min": 120000,
        "salary_max": 160000,
        "salary_currency": "USD",
        "contract_duration": None,
        "contract_worker_type": None,
        "source_url": "https://example.com/jobs/persistence-test-123",
        "application_url": "https://example.com/apply/persistence-test-123",
        "posted_at": datetime.utcnow(),
        "expires_at": None,
    }

    values.update(overrides)
    return DiscoveredJob(**values)


def test_new_job_is_persisted(db):
    job = upsert_discovered_job(db, make_job())

    assert job.id is not None
    assert job.title == "Machine Learning Engineer"
    assert job.source == "greenhouse"
    assert job.external_job_id == "persistence-test-123"

    stored_job = db.get(Job, job.id)

    assert stored_job is not None
    assert stored_job.company_id is not None


def test_company_is_created_for_new_job(db):
    job = upsert_discovered_job(db, make_job())

    company = db.get(Company, job.company_id)

    assert company is not None
    assert company.name == "Persistence Test AI"
    assert company.normalized_name == "persistence test ai"


def test_existing_company_is_reused(db):
    first_job = upsert_discovered_job(db, make_job())

    second_job = upsert_discovered_job(
        db,
        make_job(
            source_job_id="persistence-test-456",
            title="Senior Machine Learning Engineer",
        ),
    )

    assert first_job.company_id == second_job.company_id

    companies = db.query(Company).filter(
        Company.normalized_name == "persistence test ai"
    ).all()

    assert len(companies) == 1


def test_duplicate_job_is_updated(db):
    first_job = upsert_discovered_job(db, make_job())

    original_first_seen = first_job.first_seen_at

    updated_job = upsert_discovered_job(
        db,
        make_job(
            title="Senior Machine Learning Engineer",
            salary_min=140000,
            salary_max=180000,
        ),
    )

    assert updated_job.id == first_job.id
    assert updated_job.title == "Senior Machine Learning Engineer"
    assert updated_job.salary_min == 140000
    assert updated_job.salary_max == 180000
    assert updated_job.first_seen_at == original_first_seen
    assert updated_job.last_seen_at >= original_first_seen


def test_duplicate_job_does_not_create_second_record(db):
    first_job = upsert_discovered_job(db, make_job())

    second_job = upsert_discovered_job(
        db,
        make_job(
            title="Updated Machine Learning Engineer",
        ),
    )

    assert first_job.id == second_job.id

    jobs = db.query(Job).filter(
        Job.source == "greenhouse",
        Job.external_job_id == "persistence-test-123",
    ).all()

    assert len(jobs) == 1


def test_fallback_fingerprint_updates_existing_job_without_source_id(db):
    first_job = upsert_discovered_job(
        db,
        make_job(source_job_id=None),
    )

    second_job = upsert_discovered_job(
        db,
        make_job(
            source_job_id=None,
            salary_min=150000,
        ),
    )

    assert first_job.id == second_job.id
    assert second_job.salary_min == 150000

    jobs = db.query(Job).filter(
        Job.source == "greenhouse",
        Job.identity_fingerprint == first_job.identity_fingerprint,
    ).all()

    assert len(jobs) == 1


def test_fallback_fingerprint_differs_creates_new_job(db):
    first_job = upsert_discovered_job(
        db,
        make_job(source_job_id=None),
    )

    second_job = upsert_discovered_job(
        db,
        make_job(
            source_job_id=None,
            title="Staff Machine Learning Engineer",
        ),
    )

    assert first_job.id != second_job.id
    assert first_job.identity_fingerprint != second_job.identity_fingerprint

# ---------------------------------------------------------------------------
# Timestamp timezone handling
#
# jobs.posting_date/first_seen_at/last_seen_at are TIMESTAMP WITHOUT TIME
# ZONE columns holding UTC by convention. Binding an *aware* datetime to
# one makes Postgres cast timestamptz -> timestamp using the session's
# TimeZone, silently shifting the stored value on any deployment whose
# Postgres session timezone is not UTC. These tests pin the coercion that
# keeps what is stored identical regardless of that setting.
# ---------------------------------------------------------------------------


def test_aware_posted_at_is_stored_as_naive_utc(db):
    posted_at = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

    job = upsert_discovered_job(
        db,
        make_job(source_job_id="tz-aware-1", posted_at=posted_at),
    )

    stored = db.get(Job, job.id)

    assert stored.posting_date.tzinfo is None
    assert stored.posting_date == datetime(2026, 1, 15, 23, 30)


def test_naive_posted_at_is_preserved_unchanged(db):
    posted_at = datetime(2026, 1, 15, 23, 30)

    job = upsert_discovered_job(
        db,
        make_job(source_job_id="tz-naive-1", posted_at=posted_at),
    )

    assert db.get(Job, job.id).posting_date == posted_at


def test_seen_timestamps_are_naive(db):
    job = upsert_discovered_job(db, make_job(source_job_id="tz-seen-1"))

    stored = db.get(Job, job.id)

    assert stored.first_seen_at.tzinfo is None
    assert stored.last_seen_at.tzinfo is None


@pytest.mark.parametrize(
    "session_timezone", ["UTC", "America/New_York", "Asia/Kolkata"]
)
def test_timestamps_do_not_shift_with_server_timezone(db, session_timezone):
    """The same input must land in the DB identically whatever the
    Postgres session timezone is - the regression this coercion fixes."""
    db.execute(text(f"SET LOCAL TIME ZONE '{session_timezone}'"))

    posted_at = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

    job = upsert_discovered_job(
        db,
        make_job(
            source_job_id=f"tz-shift-{session_timezone}",
            posted_at=posted_at,
        ),
    )
    db.flush()
    db.expire_all()

    stored = db.get(Job, job.id)

    assert stored.posting_date == datetime(2026, 1, 15, 23, 30)
