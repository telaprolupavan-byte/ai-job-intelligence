import threading

import pytest
from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Job
from services.job_discovery.contracts import DiscoveredJob


def _fake_discovered_job(source_job_id: str, title: str) -> DiscoveredJob:
    return DiscoveredJob(
        source="greenhouse",
        source_job_id=source_job_id,
        title=title,
        company="Example Inc",
        description="Build things.",
        requirements=None,
        responsibilities=None,
        location="Remote, USA",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url=f"https://boards.greenhouse.io/example/jobs/{source_job_id}",
        application_url=f"https://boards.greenhouse.io/example/jobs/{source_job_id}",
        posted_at=None,
        expires_at=None,
    )


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_discovery_settings(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", None)
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", None
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", None
    )


def test_trigger_disabled_without_configured_token(client):
    response = client.post("/internal/job-discovery/run")
    assert response.status_code == 503


def test_trigger_rejects_missing_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "secret-1")

    response = client.post("/internal/job-discovery/run")
    assert response.status_code == 401


def test_trigger_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "secret-1")

    response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": "wrong"},
    )
    assert response.status_code == 401


def test_trigger_returns_503_when_source_not_configured_even_with_valid_token(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "secret-1")

    response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": "secret-1"},
    )
    assert response.status_code == 503


def test_trigger_runs_discovery_with_valid_token_and_configured_source(
    client, monkeypatch, db
):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "secret-1")
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    fake_job = DiscoveredJob(
        source="greenhouse",
        source_job_id="gh-500",
        title="Data Engineer",
        company="Example Inc",
        description="Build pipelines.",
        requirements=None,
        responsibilities=None,
        location="Austin, TX",
        country="USA",
        remote_type="hybrid",
        employment_type="full_time",
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url="https://boards.greenhouse.io/example/jobs/500",
        application_url="https://boards.greenhouse.io/example/jobs/500",
        posted_at=None,
        expires_at=None,
    )

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [fake_job],
    )

    response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": "secret-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "greenhouse"
    assert body["fetched"] == 1
    assert body["inserted"] == 1
    assert body["rejected"] == 0

    assert (
        db.query(Job)
        .filter(Job.source == "greenhouse", Job.external_job_id == "gh-500")
        .count()
        == 1
    )


def test_list_runs_rejects_missing_token(client):
    response = client.get("/internal/job-discovery/runs")
    assert response.status_code == 503


def test_list_runs_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "secret-1")

    response = client.get(
        "/internal/job-discovery/runs",
        headers={"X-Discovery-Trigger-Token": "wrong"},
    )
    assert response.status_code == 401


def test_list_runs_returns_recorded_runs_after_trigger(client, monkeypatch, db):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "secret-1")
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    fake_job = DiscoveredJob(
        source="greenhouse",
        source_job_id="gh-600",
        title="Platform Engineer",
        company="Example Inc",
        description="Build platforms.",
        requirements=None,
        responsibilities=None,
        location="Remote, USA",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url="https://boards.greenhouse.io/example/jobs/600",
        application_url="https://boards.greenhouse.io/example/jobs/600",
        posted_at=None,
        expires_at=None,
    )
    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [fake_job],
    )

    trigger_response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": "secret-1"},
    )
    assert trigger_response.status_code == 200

    runs_response = client.get(
        "/internal/job-discovery/runs",
        headers={"X-Discovery-Trigger-Token": "secret-1"},
    )
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) == 1
    assert runs[0]["source"] == "greenhouse"
    assert runs[0]["status"] == "succeeded"
    assert runs[0]["fetched"] == 1
    assert runs[0]["inserted"] == 1
    assert runs[0]["started_at"] is not None
    assert runs[0]["completed_at"] is not None
    assert runs[0]["error_message"] is None


def test_overlapping_triggers_reject_the_second_and_recover_afterwards(
    client, monkeypatch
):
    """End-to-end, through the real HTTP endpoint on real threads: a
    trigger that arrives while one is already in flight (e.g. the
    scheduler firing during a slow manual trigger, or two scheduler
    instances misconfigured to overlap) is rejected with 409 rather than
    running concurrently, and the lock is released afterwards so a later
    run is not permanently blocked by the earlier one."""
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "secret-1")
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    started = threading.Event()
    release = threading.Event()

    def _slow_fetch(self):
        started.set()
        release.wait(timeout=5)
        return [_fake_discovered_job("gh-slow", "Slow Fetch Role")]

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        _slow_fetch,
    )

    results = {}

    def _first_call():
        results["first"] = client.post(
            "/internal/job-discovery/run",
            headers={"X-Discovery-Trigger-Token": "secret-1"},
        )

    first_thread = threading.Thread(target=_first_call)
    first_thread.start()
    assert started.wait(timeout=5), "first call never reached fetch_jobs"

    second_response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": "secret-1"},
    )
    assert second_response.status_code == 409

    release.set()
    first_thread.join(timeout=5)
    assert not first_thread.is_alive()
    assert results["first"].status_code == 200
    assert results["first"].json()["inserted"] == 1

    # Recovery after a rejected overlap (the lock being released so a
    # later run is not permanently blocked) is covered, single-threaded,
    # by test_run_configured_discovery_rejects_overlapping_run in
    # test_job_discovery_service.py - deliberately not repeated here on a
    # second real thread against the shared test-session `db` fixture,
    # which (unlike a real request's own freshly-opened session) is not
    # safe to reuse across threads once a background thread has already
    # committed through it.
