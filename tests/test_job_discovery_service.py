import pytest

from apps.api.config import settings
from apps.api.models import DiscoveryRun, Job
from apps.api.services import job_discovery_service
from apps.api.services.job_discovery_service import (
    JobDiscoveryNotConfiguredError,
    JobDiscoveryServiceError,
    build_configured_source,
    build_configured_sources,
    run_configured_discovery,
)
from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.sources.greenhouse import GreenhouseAdapterError
from services.job_discovery.sources.theirstack import TheirStackAdapterError


def _sample_discovered_job(
    source="greenhouse", source_job_id="gh-1", title="Backend Engineer"
):
    return DiscoveredJob(
        source=source,
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
        source_url=f"https://example.test/jobs/{source_job_id}",
        application_url=f"https://example.test/jobs/{source_job_id}",
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
    monkeypatch.setattr(settings, "theirstack_enabled", False)
    monkeypatch.setattr(settings, "theirstack_api_key", None)


def _enable_greenhouse(monkeypatch):
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_board_token", "example"
    )
    monkeypatch.setattr(
        settings, "job_discovery_greenhouse_company_name", "Example Inc"
    )


def _enable_theirstack(monkeypatch, api_key="ts-secret-key"):
    monkeypatch.setattr(settings, "theirstack_enabled", True)
    monkeypatch.setattr(settings, "theirstack_api_key", api_key)


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


def test_build_configured_sources_includes_only_greenhouse_when_theirstack_disabled(
    monkeypatch,
):
    _enable_greenhouse(monkeypatch)

    sources = build_configured_sources()

    assert [s.source_name for s in sources] == ["greenhouse"]


def test_build_configured_sources_skips_theirstack_when_enabled_without_key(
    monkeypatch,
):
    _enable_greenhouse(monkeypatch)
    monkeypatch.setattr(settings, "theirstack_enabled", True)
    monkeypatch.setattr(settings, "theirstack_api_key", None)

    sources = build_configured_sources()

    assert [s.source_name for s in sources] == ["greenhouse"]


def test_build_configured_sources_includes_theirstack_when_configured(
    monkeypatch,
):
    _enable_theirstack(monkeypatch)

    sources = build_configured_sources()

    assert [s.source_name for s in sources] == ["theirstack"]


def test_build_configured_sources_includes_both_when_both_configured(
    monkeypatch,
):
    _enable_greenhouse(monkeypatch)
    _enable_theirstack(monkeypatch)

    sources = build_configured_sources()

    assert [s.source_name for s in sources] == ["greenhouse", "theirstack"]


def test_run_configured_discovery_raises_when_unconfigured(db):
    with pytest.raises(JobDiscoveryNotConfiguredError):
        run_configured_discovery(db)


def test_run_configured_discovery_persists_fetched_jobs(db, monkeypatch):
    _enable_greenhouse(monkeypatch)

    fake_jobs = [
        _sample_discovered_job(source_job_id="gh-1", title="Backend Engineer"),
        _sample_discovered_job(source_job_id="gh-2", title="Frontend Engineer"),
    ]

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: fake_jobs,
    )

    summaries = run_configured_discovery(db)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.source == "greenhouse"
    assert summary.status == "succeeded"
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
    _enable_greenhouse(monkeypatch)

    us_job = _sample_discovered_job(source_job_id="gh-1", title="Backend Engineer")
    non_us_job = _sample_discovered_job(
        source_job_id="gh-2", title="Remote EU Engineer"
    )
    non_us_job.country = ""

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [us_job, non_us_job],
    )

    summaries = run_configured_discovery(db)

    assert summaries[0].fetched == 2
    assert summaries[0].inserted == 1
    assert summaries[0].rejected == 1
    assert len(summaries[0].rejected_reasons) == 1


def test_run_configured_discovery_isolates_adapter_failure_to_its_source(
    db, monkeypatch
):
    """A source fetch failure (e.g. the board is unreachable) is recorded
    as a failed summary for that source - it does not raise and does not
    prevent other configured sources from running. This is a deliberate
    behavior change from the single-source design: with two
    independently-enabled providers, one provider's outage can no longer
    be allowed to fail the whole discovery run."""
    _enable_greenhouse(monkeypatch)

    def _raise(self):
        raise GreenhouseAdapterError("board unreachable")

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        _raise,
    )

    summaries = run_configured_discovery(db)

    assert len(summaries) == 1
    assert summaries[0].source == "greenhouse"
    assert summaries[0].status == "failed"
    assert "board unreachable" in summaries[0].error

    assert db.query(Job).filter(Job.source == "greenhouse").count() == 0


def test_theirstack_fetch_failure_does_not_block_greenhouse(db, monkeypatch):
    _enable_greenhouse(monkeypatch)
    _enable_theirstack(monkeypatch)

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [_sample_discovered_job(source_job_id="gh-1")],
    )

    def _raise(self):
        raise TheirStackAdapterError("TheirStack authentication failed (HTTP 401).")

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.TheirStackJobSource"
        ".fetch_jobs",
        _raise,
    )

    summaries = run_configured_discovery(db)

    by_source = {s.source: s for s in summaries}
    assert by_source["greenhouse"].status == "succeeded"
    assert by_source["greenhouse"].inserted == 1
    assert by_source["theirstack"].status == "failed"
    assert "authentication failed" in by_source["theirstack"].error

    assert db.query(Job).filter(Job.source == "greenhouse").count() == 1
    assert db.query(Job).filter(Job.source == "theirstack").count() == 0


def test_theirstack_jobs_are_persisted_through_the_same_pipeline(
    db, monkeypatch
):
    _enable_theirstack(monkeypatch)

    fake_job = _sample_discovered_job(
        source="theirstack", source_job_id="ts-1", title="Data Engineer"
    )

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.TheirStackJobSource"
        ".fetch_jobs",
        lambda self: [fake_job],
    )

    summaries = run_configured_discovery(db)

    assert summaries[0].source == "theirstack"
    assert summaries[0].status == "succeeded"
    assert summaries[0].inserted == 1

    persisted = db.query(Job).filter(Job.source == "theirstack").one()
    assert persisted.title == "Data Engineer"
    assert persisted.is_active is True

    run = db.query(DiscoveryRun).filter(DiscoveryRun.source == "theirstack").one()
    assert run.status == "succeeded"
    assert run.inserted_count == 1


def test_source_failure_does_not_invalidate_existing_jobs(db, monkeypatch):
    _enable_greenhouse(monkeypatch)

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [
            _sample_discovered_job(source_job_id="gh-existing", title="Existing Role")
        ],
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

    summaries = run_configured_discovery(db)
    assert summaries[0].status == "failed"

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
    _enable_greenhouse(monkeypatch)
    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [_sample_discovered_job(source_job_id="gh-1")],
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
    _enable_greenhouse(monkeypatch)

    def _raise(self):
        raise GreenhouseAdapterError("board unreachable")

    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        _raise,
    )

    run_configured_discovery(db)

    run = db.query(DiscoveryRun).filter(DiscoveryRun.source == "greenhouse").one()
    assert run.status == "failed"
    assert "board unreachable" in run.error_message
    assert run.completed_at is not None


def test_run_configured_discovery_raises_on_database_failure_during_commit(
    db, monkeypatch
):
    _enable_greenhouse(monkeypatch)
    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [
            _sample_discovered_job(source_job_id="gh-db-fail", title="DB Failure Role")
        ],
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


def test_run_configured_discovery_rejects_overlapping_run(db, monkeypatch):
    """A second call while one is already in flight must be rejected
    (409) rather than run concurrently - see _discovery_lock's docstring
    for why a plain in-process lock is the right (and only necessary)
    mechanism given this app's single-worker deployment."""
    _enable_greenhouse(monkeypatch)

    acquired = job_discovery_service._discovery_lock.acquire(blocking=False)
    assert acquired, "sanity check: lock should start free"

    try:
        with pytest.raises(JobDiscoveryServiceError) as exc_info:
            run_configured_discovery(db)
        assert exc_info.value.status_code == 409
    finally:
        job_discovery_service._discovery_lock.release()

    # A rejected overlapping attempt never touched the source or the DB -
    # it isn't a "run" for observability purposes.
    assert db.query(DiscoveryRun).count() == 0

    # The lock was released - a rejected overlap must not permanently
    # block later scheduled runs.
    monkeypatch.setattr(
        "apps.api.services.job_discovery_service.GreenhouseJobSource"
        ".fetch_jobs",
        lambda self: [
            _sample_discovered_job(source_job_id="gh-recovery", title="Recovery Role")
        ],
    )
    summaries = run_configured_discovery(db)
    assert summaries[0].inserted == 1
    assert (
        db.query(DiscoveryRun)
        .filter(DiscoveryRun.source == "greenhouse", DiscoveryRun.status == "succeeded")
        .count()
        == 1
    )
