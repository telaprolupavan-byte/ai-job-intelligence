"""AJI-028 - provider-stated job expiration: persisted from
`DiscoveredJob.expires_at`, enforced at query time by the shared
`active_jobs_filter()` (GET /jobs, the dashboard, and - through
`job_listing_query` - GET /jobs/priority), and never inferred from a job
not being seen by a discovery run.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.main import app
from apps.api.models import Company, Job, User
from apps.api.security import create_access_token
from apps.api.services.job_access import active_jobs_filter
from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.persistence import upsert_discovered_job
from services.job_discovery.pipeline import (
    normalize_raw_jobs,
    run_discovery_pipeline,
)
from tests.support.job_discovery import (
    ExamplePagedSource,
    PagedTransport,
    example_record,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def discovered(**overrides) -> DiscoveredJob:
    values = {
        "source": "expiry_test_source",
        "source_job_id": f"exp-{uuid4().hex}",
        "title": "Data Engineer",
        "company": "Expiry Test Co",
        "description": "Build and operate data pipelines end to end.",
        "requirements": None,
        "responsibilities": None,
        "location": "Remote",
        "country": "USA",
        "remote_type": "remote",
        "employment_type": "full_time",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "contract_duration": None,
        "contract_worker_type": None,
        "source_url": "https://jobs.expiry.example/1",
        "application_url": None,
        "posted_at": None,
        "expires_at": None,
    }
    values.update(overrides)
    return DiscoveredJob(**values)


@pytest.fixture(autouse=True)
def _discovery_settings(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_provider", None)
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"expiry-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _job(db, *, title: str, expires_at=None, is_active=True, **fields) -> Job:
    company = Company(name="Expiry Test Co", normalized_name="expiry test co")
    db.add(company)
    db.flush()
    now = _utcnow()
    job = Job(
        company_id=company.id,
        title=title,
        country="USA",
        description=f"{title} role description with enough detail.",
        source="greenhouse",
        is_active=is_active,
        expires_at=expires_at,
        first_seen_at=now,
        last_seen_at=now,
        **fields,
    )
    db.add(job)
    db.flush()
    return job


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_stated_expiry_is_persisted_as_naive_utc(db):
    # 17:00 at -05:00 is 22:00 UTC.
    aware = datetime(2026, 12, 31, 17, 0, tzinfo=timezone(timedelta(hours=-5)))

    job = upsert_discovered_job(db, discovered(expires_at=aware))

    assert job.expires_at == datetime(2026, 12, 31, 22, 0)
    assert db.get(Job, job.id).expires_at.tzinfo is None


def test_no_stated_expiry_is_stored_as_null(db):
    job = upsert_discovered_job(db, discovered())

    assert job.expires_at is None


def test_update_mirrors_the_provider_extending_or_dropping_the_expiry(db):
    job_id = f"exp-{uuid4().hex}"
    first = datetime(2026, 10, 1)
    extended = datetime(2026, 11, 1)

    job = upsert_discovered_job(db, discovered(source_job_id=job_id, expires_at=first))
    assert job.expires_at == first

    job = upsert_discovered_job(
        db, discovered(source_job_id=job_id, expires_at=extended)
    )
    assert job.expires_at == extended

    job = upsert_discovered_job(db, discovered(source_job_id=job_id))
    assert job.expires_at is None


# ---------------------------------------------------------------------------
# active_jobs_filter
# ---------------------------------------------------------------------------


def _ids_matching(db, now=None) -> set:
    return {
        row.id for row in db.query(Job).filter(active_jobs_filter(now)).all()
    }


def test_active_jobs_filter_semantics(db):
    now = datetime(2026, 9, 24, 12, 0)
    open_no_expiry = _job(db, title="No expiry")
    open_future = _job(db, title="Future", expires_at=now + timedelta(minutes=1))
    expired = _job(db, title="Expired", expires_at=now - timedelta(minutes=1))
    at_boundary = _job(db, title="Boundary", expires_at=now)
    inactive = _job(db, title="Inactive", is_active=False)

    matching = _ids_matching(db, now)

    assert open_no_expiry.id in matching
    assert open_future.id in matching
    assert expired.id not in matching
    assert at_boundary.id not in matching  # expires *at* now = closed
    assert inactive.id not in matching


def test_active_jobs_filter_accepts_an_aware_now(db):
    expires = datetime(2026, 9, 24, 12, 0)
    job = _job(db, title="Aware", expires_at=expires)

    # 11:30 at -01:00 is 12:30 UTC: past the expiry.
    aware_now = datetime(2026, 9, 24, 11, 30, tzinfo=timezone(timedelta(hours=-1)))

    assert job.id not in _ids_matching(db, aware_now)


def test_active_jobs_filter_defaults_to_the_current_time(db):
    past = _job(db, title="Past", expires_at=_utcnow() - timedelta(days=1))
    future = _job(db, title="Future", expires_at=_utcnow() + timedelta(days=1))

    matching = _ids_matching(db)

    assert past.id not in matching
    assert future.id in matching


# ---------------------------------------------------------------------------
# API surfaces
# ---------------------------------------------------------------------------


def test_jobs_listing_hides_expired_jobs_and_reports_expires_at(client, db):
    user = _user(db)
    token = f"zq{uuid4().hex[:10]}"
    future = _utcnow() + timedelta(days=3)
    open_job = _job(db, title=f"{token} open", expires_at=future)
    no_expiry = _job(db, title=f"{token} no expiry")
    _job(db, title=f"{token} expired", expires_at=_utcnow() - timedelta(days=1))

    response = client.get("/jobs", params={"search": token}, headers=_auth(user))

    assert response.status_code == 200
    jobs = {job["id"]: job for job in response.json()["jobs"]}
    assert set(jobs) == {str(open_job.id), str(no_expiry.id)}
    assert jobs[str(open_job.id)]["expires_at"] == future.isoformat()
    assert jobs[str(no_expiry.id)]["expires_at"] is None
    assert response.json()["pagination"]["total"] == 2


def test_expired_job_stays_readable_by_id(client, db):
    # Unchanged per-job behavior: a user who already opened a job (e.g.
    # it is tracked as an application) can still read it after it closes.
    user = _user(db)
    job = _job(db, title="Closed role", expires_at=_utcnow() - timedelta(days=1))

    response = client.get(f"/jobs/{job.id}", headers=_auth(user))

    assert response.status_code == 200
    assert response.json()["expires_at"] is not None


def test_dashboard_counts_exclude_expired_jobs(client, db):
    user = _user(db)
    _job(db, title="Open FT", employment_type="full_time")
    _job(
        db,
        title="Expired FT",
        employment_type="full_time",
        expires_at=_utcnow() - timedelta(hours=1),
    )
    _job(
        db,
        title="Open contract",
        employment_type="contract",
        expires_at=_utcnow() + timedelta(days=1),
    )

    data = client.get("/dashboard", headers=_auth(user)).json()

    assert data["jobs"]["today_count"] == 2
    assert data["jobs"]["full_time_count"] == 1
    assert data["jobs"]["contract_count"] == 1
    assert {job["title"] for job in data["jobs"]["recent"]} == {
        "Open FT",
        "Open contract",
    }


# ---------------------------------------------------------------------------
# End to end through the pipeline, and no "not seen" inference
# ---------------------------------------------------------------------------


def _run(db, records, *, page_size=2):
    source = ExamplePagedSource(PagedTransport(records, page_size=page_size))
    normalized, errors = normalize_raw_jobs(source, source.fetch_raw_jobs())
    return run_discovery_pipeline(db, normalized), errors


def test_provider_expiry_flows_from_fetch_to_the_stored_job(db):
    expires_unix = int(datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp())
    result, errors = _run(
        db,
        [
            example_record("e2e-exp", expires=expires_unix),
            example_record("e2e-none"),
            example_record("e2e-world", countries=[]),
        ],
    )

    stored = {job.external_job_id.rsplit("/", 1)[1]: job for job in result.inserted}
    assert set(stored) == {"e2e-exp", "e2e-none"}
    assert stored["e2e-exp"].expires_at == datetime(2026, 12, 1)
    assert stored["e2e-none"].expires_at is None
    # Worldwide (no explicit U.S. eligibility) is rejected by validation.
    assert [r.reason for r in result.rejected] == [
        "Missing required fields: country"
    ]
    assert errors == []


def test_a_job_missing_from_a_later_run_is_not_marked_closed(db):
    first, _ = _run(db, [example_record("seen-1"), example_record("seen-2")])
    before = {job.id: job.last_seen_at for job in first.inserted}

    # The next run only sees one of them (e.g. it fell out of the page
    # window). Nothing may be inferred about the other.
    _run(db, [example_record("seen-1")])

    for job_id, last_seen in before.items():
        job = db.get(Job, job_id)
        assert job.is_active is True
        assert job.expires_at is None

    missing = next(
        db.get(Job, job_id)
        for job_id in before
        if db.get(Job, job_id).external_job_id.endswith("seen-2")
    )
    assert missing.last_seen_at == before[missing.id]
    assert missing.id in _ids_matching(db)
