import pytest

from apps.api.config import settings
from apps.api.models import DiscoveryRun, Job
from apps.api.services.job_discovery_service import (
    JobDiscoveryNotConfiguredError,
    JobDiscoveryServiceError,
    build_configured_source,
    run_configured_discovery,
)
from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.sources.greenhouse import GreenhouseAdapterError


def _sample_discovered_job(source_job_id="gh-1", title="Backend Engineer"):
    return DiscoveredJob(
        source="greenhouse",
        source_job_id=source_job_id,
        title=title,
        company="Example Inc",
        description="Build things.",
        requirements=None,
        responsibilities=None,
        location="New York, NY",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url="https://boards.greenhouse.io/example/jobs/1",
        application_url="https://boards.greenhouse.io/example/jobs/1",
        posted_at=None,
        expires_at=None,
    )


@pytest.fixture(autouse=True)
def _clear_discovery_settings(monkeypatch):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", None
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", None
    )


def test_build_configured_source_raises_when_unconfigured():
    with pytest.raises(JobDiscoveryNotConfiguredError):
        build_configured_source()


def test_build_configured_source_raises_when_only_board_token_set(
    monkeypatch,
):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )

    with pytest.raises(JobDiscoveryNotConfiguredError):
        build_configured_source()


def test_run_configured_discovery_raises_when_unconfigured(db):
    with pytest.raises(JobDiscoveryNotConfiguredError):
        run_configured_discovery(db)


def test_run_configured_discovery_persists_fetched_jobs(db, monkeypatch):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    fake_jobs = [
        _sample_discovered_job("gh-1", "Backend Engineer"),
        _sample_discovered_job("gh-2", "Frontend Engineer"),
    ]

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: fake_jobs,
    )

    summary = run_configured_discovery(db)

    assert summary.source == "greenhouse"
    assert summary.fetched == 2
    assert summary.inserted == 2
    assert summary.updated == 0
    assert summary.rejected == 0

    persisted_titles = {
        job.title
        for job in db.query(Job)
        .filter(Job.source == "greenhouse")
        .all()
    }
    assert persisted_titles == {"Backend Engineer", "Frontend Engineer"}


# Cross-run dedup/update behavior (same source_job_id re-ingested, or the
# fallback identity fingerprint) is already exhaustively covered at the
# pipeline/persistence layer without needing a second `db.commit()` in the
# same test session: tests/test_job_pipeline.py::
# test_repeated_ingestion_updates_existing_job and every test in
# tests/test_job_persistence.py. This module only needs to prove the new
# orchestration wiring (config gating, adapter invocation, error mapping)
# calls that already-proven pipeline correctly - not re-prove dedup itself.


def test_run_configured_discovery_rejects_non_us_jobs_without_stopping(
    db, monkeypatch
):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    us_job = _sample_discovered_job("gh-1", "Backend Engineer")
    non_us_job = _sample_discovered_job("gh-2", "Remote EU Engineer")
    non_us_job.country = ""

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [us_job, non_us_job],
    )

    summary = run_configured_discovery(db)

    assert summary.fetched == 2
    assert summary.inserted == 1
    assert summary.rejected == 1
    assert len(summary.rejected_reasons) == 1


def test_run_configured_discovery_surfaces_adapter_failure(db, monkeypatch):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    def _raise(self):
        raise GreenhouseAdapterError("board unreachable")

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        _raise,
    )

    with pytest.raises(JobDiscoveryServiceError) as exc_info:
        run_configured_discovery(db)

    assert exc_info.value.status_code == 502
    assert "board unreachable" in str(exc_info.value)

    assert db.query(Job).filter(Job.source == "greenhouse").count() == 0


def test_source_failure_does_not_invalidate_existing_jobs(db, monkeypatch):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [_sample_discovered_job("gh-existing", "Existing Role")],
    )
    run_configured_discovery(db)
    assert (
        db.query(Job)
        .filter(Job.source == "greenhouse", Job.external_job_id == "gh-existing")
        .count()
        == 1
    )

    def _raise(self):
        raise GreenhouseAdapterError("board unreachable")

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        _raise,
    )

    with pytest.raises(JobDiscoveryServiceError):
        run_configured_discovery(db)

    still_present = (
        db.query(Job)
        .filter(Job.source == "greenhouse", Job.external_job_id == "gh-existing")
        .one()
    )
    assert still_present.title == "Existing Role"
    assert still_present.is_active is True


def test_run_configured_discovery_records_discovery_run_on_success(
    db, monkeypatch
):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )
    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [_sample_discovered_job("gh-1", "Backend Engineer")],
    )

    run_configured_discovery(db)

    run = db.query(DiscoveryRun).filter(DiscoveryRun.source == "greenhouse").one()
    assert run.status == "succeeded"
    assert run.fetched_count == 1
    assert run.inserted_count == 1
    assert run.updated_count == 0
    assert run.rejected_count == 0
    assert run.error_message is None
    assert run.started_at is not None
    assert run.completed_at is not None


def test_run_configured_discovery_records_discovery_run_on_adapter_failure(
    db, monkeypatch
):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )

    def _raise(self):
        raise GreenhouseAdapterError("board unreachable")

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        _raise,
    )

    with pytest.raises(JobDiscoveryServiceError):
        run_configured_discovery(db)

    run = db.query(DiscoveryRun).filter(DiscoveryRun.source == "greenhouse").one()
    assert run.status == "failed"
    assert "board unreachable" in run.error_message
    assert run.completed_at is not None


def test_run_configured_discovery_raises_on_database_failure_during_commit(
    db, monkeypatch
):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )
    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [_sample_discovered_job("gh-db-fail", "DB Failure Role")],
    )
    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.run_discovery_pipeline",
        lambda db_, jobs: (_ for _ in ()).throw(
            Exception("simulated database outage")
        ),
    )

    with pytest.raises(JobDiscoveryServiceError) as exc_info:
        run_configured_discovery(db)

    assert exc_info.value.status_code == 503
    assert "simulated database outage" in str(exc_info.value)

    # The session is left with an unflushed/aborted transaction after a
    # failure like this - exactly as it would be for the real request
    # session, which get_db() rolls back on close. Do the same here
    # before asserting on state with the same session.
    db.rollback()

    # No job data or run record should have been half-persisted.
    assert (
        db.query(Job)
        .filter(Job.source == "greenhouse", Job.external_job_id == "gh-db-fail")
        .count()
        == 0
    )
    assert db.query(DiscoveryRun).filter(DiscoveryRun.source == "greenhouse").count() == 0
