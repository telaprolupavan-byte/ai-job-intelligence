"""AJI-024: the end-to-end discovery product pipeline against a real DB -
execution counters, repeat-run deduplication, trigger security, AJI-022
privacy, test-fixture isolation, and the user-facing status endpoint."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import DiscoveryRun, Job, User
from apps.api.security import create_access_token
from apps.api.services.job_discovery_service import (
    JobDiscoveryServiceError,
    JobDiscoveryTestProviderDisabledError,
    JobDiscoveryUnknownProviderError,
    build_configured_source,
    run_configured_discovery,
)
from services.job_discovery.sources.test_fixture import (
    TEST_FIXTURE_SOURCE,
    TestFixtureJobSource,
)


TOKEN = "aji-024-trigger-secret"


@pytest.fixture(autouse=True)
def _discovery_settings(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", None)
    monkeypatch.setattr(settings, "job_discovery_greenhouse_board_token", None)
    monkeypatch.setattr(settings, "job_discovery_greenhouse_company_name", None)
    monkeypatch.setattr(settings, "job_discovery_provider", None)
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)


@pytest.fixture
def test_mode(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_provider", "test_fixture")
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", True)


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"discovery-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _run_as_separate_request(db):
    """Run discovery in its own session on the test connection, as a
    second trigger request would in production (each request gets a fresh
    session). The shared `db` fixture cannot commit twice in one session -
    see the note in tests/test_job_discovery_service.py."""
    session = Session(
        bind=db.connection(), join_transaction_mode="create_savepoint"
    )
    try:
        return run_configured_discovery(session)
    finally:
        session.close()


def _fixture_jobs(db) -> list[Job]:
    return db.query(Job).filter(Job.source == TEST_FIXTURE_SOURCE).all()


# ---------------------------------------------------------------------------
# Provider selection / isolation
# ---------------------------------------------------------------------------


def test_test_provider_requires_explicit_enable_flag(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_provider", "test_fixture")

    with pytest.raises(JobDiscoveryTestProviderDisabledError) as exc_info:
        build_configured_source()

    assert exc_info.value.status_code == 503


def test_enable_flag_alone_does_not_select_test_provider(monkeypatch, db):
    """Turning the flag on never silently swaps the production provider."""
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", True)

    with pytest.raises(JobDiscoveryServiceError):
        run_configured_discovery(db)

    assert _fixture_jobs(db) == []


def test_unknown_provider_is_rejected_not_defaulted(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_provider", "lever")

    with pytest.raises(JobDiscoveryUnknownProviderError):
        build_configured_source()


def test_test_mode_selects_fixture_provider(test_mode):
    assert isinstance(build_configured_source(), TestFixtureJobSource)


# ---------------------------------------------------------------------------
# Discovery execution counters, inserts, updates, rejects, duplicates
# ---------------------------------------------------------------------------


def test_first_run_counters(db, test_mode):
    summary = run_configured_discovery(db)

    assert summary.source == TEST_FIXTURE_SOURCE
    assert summary.is_test_data is True
    assert summary.fetched == 9
    assert summary.normalized == 8
    assert summary.rejected == 4  # 1 malformed + title + placeholder + non-US
    assert summary.duplicates == 1
    assert summary.inserted == 4
    assert summary.updated == 0
    assert summary.accepted == 4
    assert summary.fetched == summary.normalized + 1
    assert summary.normalized == (
        summary.accepted + (summary.rejected - 1) + summary.duplicates
    )
    assert len(summary.rejected_reasons) == 4

    run = db.query(DiscoveryRun).filter(
        DiscoveryRun.source == TEST_FIXTURE_SOURCE
    ).one()
    assert run.status == "succeeded"
    assert (run.fetched_count, run.normalized_count) == (9, 8)
    assert (run.inserted_count, run.updated_count) == (4, 0)
    assert (run.rejected_count, run.duplicate_count) == (4, 1)


def test_repeated_discovery_creates_no_duplicates(db, test_mode):
    _run_as_separate_request(db)
    first_ids = {job.id for job in _fixture_jobs(db)}

    summary = _run_as_separate_request(db)

    assert summary.inserted == 0
    assert summary.updated == 4
    assert summary.duplicates == 1
    assert {job.id for job in _fixture_jobs(db)} == first_ids
    assert len(first_ids) == 4


def test_distinct_jobs_remain_separate_and_fields_persist(db, test_mode):
    run_configured_discovery(db)
    jobs = {job.external_job_id: job for job in _fixture_jobs(db)}

    assert set(jobs) == {"fx-1001", "fx-1002", "fx-1003", None}

    full_time = jobs["fx-1001"]
    assert full_time.employment_type == "full_time"
    assert full_time.remote_type == "hybrid"
    assert full_time.source_url.endswith("/fx-1001")

    contract = jobs["fx-1002"]
    assert contract.employment_type == "contract"
    assert contract.contract_duration == "6 months"
    assert contract.application_url is None

    assert jobs["fx-1003"].application_url is None  # javascript: dropped
    assert jobs[None].identity_fingerprint is not None


# ---------------------------------------------------------------------------
# Trigger security
# ---------------------------------------------------------------------------


def test_trigger_disabled_without_configured_secret(client, test_mode, db):
    response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": TOKEN},
    )

    assert response.status_code == 503
    assert _fixture_jobs(db) == []


def test_trigger_rejects_missing_secret(client, monkeypatch, test_mode, db):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", TOKEN)

    response = client.post("/internal/job-discovery/run")

    assert response.status_code == 401
    assert _fixture_jobs(db) == []


def test_trigger_rejects_invalid_secret(client, monkeypatch, test_mode, db):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", TOKEN)

    for bad in ("wrong", TOKEN[:-1], TOKEN + "x", " " + TOKEN):
        response = client.post(
            "/internal/job-discovery/run",
            headers={"X-Discovery-Trigger-Token": bad},
        )
        assert response.status_code == 401

    assert _fixture_jobs(db) == []


def test_normal_user_jwt_cannot_trigger_discovery(
    client, monkeypatch, test_mode, db
):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", TOKEN)
    user = _make_user(db)

    response = client.post(
        "/internal/job-discovery/run", headers=_auth(user)
    )

    assert response.status_code == 401
    assert _fixture_jobs(db) == []


def test_authorized_trigger_returns_operational_counters(
    client, monkeypatch, test_mode
):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", TOKEN)

    response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": TOKEN},
    )

    assert response.status_code == 200
    body = response.json()
    assert {
        key: body[key]
        for key in (
            "fetched",
            "normalized",
            "accepted",
            "rejected",
            "duplicates",
            "inserted",
            "updated",
        )
    } == {
        "fetched": 9,
        "normalized": 8,
        "accepted": 4,
        "rejected": 4,
        "duplicates": 1,
        "inserted": 4,
        "updated": 0,
    }
    assert body["is_test_data"] is True

    runs = client.get(
        "/internal/job-discovery/runs",
        headers={"X-Discovery-Trigger-Token": TOKEN},
    ).json()
    assert runs[0]["duplicates"] == 1
    assert runs[0]["normalized"] == 8
    assert runs[0]["accepted"] == 4


def test_trigger_with_disabled_test_provider_is_503(client, monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", TOKEN)
    monkeypatch.setattr(settings, "job_discovery_provider", "test_fixture")

    response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": TOKEN},
    )

    assert response.status_code == 503
    assert "JOB_DISCOVERY_ENABLE_TEST_PROVIDER" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Privacy (AJI-022)
# ---------------------------------------------------------------------------


def test_discovered_jobs_are_shared_and_never_owned(client, db, test_mode):
    run_configured_discovery(db)
    alice, bob = _make_user(db), _make_user(db)

    for job in _fixture_jobs(db):
        assert job.submitted_by_user_id is None
        assert job.raw_submitted_content is None

    for user in (alice, bob):
        body = client.get("/jobs", headers=_auth(user)).json()
        fixture = [j for j in body["jobs"] if j["source"] == TEST_FIXTURE_SOURCE]
        assert len(fixture) == 4
        assert {j["origin"] for j in fixture} == {"discovered"}
        assert {j["is_test_data"] for j in fixture} == {True}


def test_user_submitted_job_stays_private_through_discovery(
    client, db, test_mode
):
    owner, other = _make_user(db), _make_user(db)
    private = Job(
        title="My pasted job",
        country="USA",
        description="Private content pasted by the owner.",
        source="user_submitted",
        submitted_by_user_id=owner.id,
        raw_submitted_content="Private content pasted by the owner.",
        is_active=True,
    )
    db.add(private)
    db.flush()

    run_configured_discovery(db)
    db.refresh(private)

    assert private.submitted_by_user_id == owner.id
    assert private.title == "My pasted job"

    owner_jobs = client.get("/jobs", headers=_auth(owner)).json()["jobs"]
    other_jobs = client.get("/jobs", headers=_auth(other)).json()["jobs"]

    owned = [j for j in owner_jobs if j["id"] == str(private.id)]
    assert owned and owned[0]["origin"] == "user_submitted"
    assert owned[0]["is_test_data"] is False
    assert all(j["id"] != str(private.id) for j in other_jobs)
    assert (
        client.get(f"/jobs/{private.id}", headers=_auth(other)).status_code
        == 404
    )


def test_discovery_never_updates_a_private_row_with_matching_identity(
    db, test_mode
):
    """Even a private row sharing a provider's (source, external id) is
    never matched and overwritten by discovery."""
    owner = _make_user(db)
    private = Job(
        title="Private copy",
        country="USA",
        description="Owner's private job with a colliding identity.",
        source=TEST_FIXTURE_SOURCE,
        external_job_id="fx-1002",
        submitted_by_user_id=owner.id,
        is_active=True,
    )
    db.add(private)
    db.flush()

    summary = run_configured_discovery(db)
    db.refresh(private)

    assert private.title == "Private copy"
    assert private.submitted_by_user_id == owner.id
    assert summary.updated == 0


# ---------------------------------------------------------------------------
# Test-fixture isolation from production reads
# ---------------------------------------------------------------------------


def test_fixture_jobs_hidden_when_test_mode_is_off(
    client, db, monkeypatch, test_mode
):
    run_configured_discovery(db)
    user = _make_user(db)
    fixture_id = str(_fixture_jobs(db)[0].id)

    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)

    body = client.get("/jobs", headers=_auth(user)).json()
    assert all(j["source"] != TEST_FIXTURE_SOURCE for j in body["jobs"])
    anonymous = client.get("/jobs").json()["jobs"]
    assert all(j["source"] != TEST_FIXTURE_SOURCE for j in anonymous)
    assert (
        client.get(f"/jobs/{fixture_id}", headers=_auth(user)).status_code
        == 404
    )
    dashboard = client.get("/dashboard", headers=_auth(user))
    assert dashboard.status_code == 200
    assert TEST_FIXTURE_SOURCE not in dashboard.text


# ---------------------------------------------------------------------------
# User-facing status endpoint
# ---------------------------------------------------------------------------


def test_status_requires_authentication(client):
    assert client.get("/job-discovery/status").status_code == 401


def test_status_when_no_source_configured(client, db):
    user = _make_user(db)

    body = client.get("/job-discovery/status", headers=_auth(user)).json()

    assert body["source_configured"] is False
    assert body["test_mode"] is False


def test_status_reports_test_mode_and_last_run_without_secrets(
    client, db, monkeypatch, test_mode
):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", TOKEN)
    run_configured_discovery(db)
    user = _make_user(db)

    response = client.get("/job-discovery/status", headers=_auth(user))

    body = response.json()
    assert body["source_configured"] is True
    assert body["test_mode"] is True
    assert body["last_run"]["status"] == "succeeded"
    assert TOKEN not in response.text
    assert "error" not in response.text


def test_status_ignores_fixture_runs_outside_test_mode(
    client, db, monkeypatch, test_mode
):
    run_configured_discovery(db)
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)
    monkeypatch.setattr(settings, "job_discovery_provider", None)
    user = _make_user(db)

    body = client.get("/job-discovery/status", headers=_auth(user)).json()

    assert body["test_mode"] is False
    assert body["source_configured"] is False
    non_fixture_runs = (
        db.query(DiscoveryRun)
        .filter(DiscoveryRun.source != TEST_FIXTURE_SOURCE)
        .count()
    )
    if non_fixture_runs == 0:
        assert body["last_run"] is None
