import pytest
from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Job
from services.job_discovery.contracts import DiscoveredJob


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
