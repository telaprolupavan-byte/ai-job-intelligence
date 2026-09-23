"""Job Discovery orchestration service.

This is the operational layer between an ops-triggered request and the
pure, DB-free `services.job_discovery` pipeline (source adapter ->
normalize -> validate -> deduplicate -> persist). The pipeline itself has
existed and been fully unit-tested since AJI-006; nothing in the running
application ever invoked it. This module is that missing invocation path.

Which company board(s) to actually ingest is a product/legal decision
(whose public postings AJI has permission to aggregate), not something to
hardcode here - `settings.job_discovery_greenhouse_board_token` /
`job_discovery_greenhouse_company_name` are unset by default, and
`run_configured_discovery` raises a clear, typed error until an operator
configures them.

AJI-024: providers go through the formal adapter boundary
(`services/job_discovery/sources/base.py`): fetch raw records, normalize
each one deterministically (a malformed record is a rejection, not a
failed run), then the shared validate/deduplicate/persist pipeline. The
synthetic `test_fixture` provider exists for tests and local development
and is double-gated - see `build_configured_source`.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import DiscoveryRun
from services.job_discovery.pipeline import (
    PipelineResult,
    SourceDiscoveryResult,
    normalize_raw_jobs,
    run_discovery_pipeline,
)
from services.job_discovery.sources.base import (
    JobSourceAdapter,
    JobSourceFetchError,
)
from services.job_discovery.sources.greenhouse import GreenhouseJobSource
from services.job_discovery.sources.test_fixture import (
    TEST_FIXTURE_SOURCE,
    TestFixtureJobSource,
)


logger = logging.getLogger(__name__)

# String column limit on DiscoveryRun.error_message - truncate so an
# unusually long exception message can never fail that write too.
_ERROR_MESSAGE_MAX_LEN = 1000


class JobDiscoveryServiceError(Exception):
    def __init__(self, message: str, *, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class JobDiscoveryNotConfiguredError(JobDiscoveryServiceError):
    def __init__(self) -> None:
        super().__init__(
            "Job discovery has no configured source. Set "
            "JOB_DISCOVERY_GREENHOUSE_BOARD_TOKEN and "
            "JOB_DISCOVERY_GREENHOUSE_COMPANY_NAME to enable it.",
            status_code=503,
        )


class JobDiscoveryTestProviderDisabledError(JobDiscoveryServiceError):
    def __init__(self) -> None:
        super().__init__(
            "JOB_DISCOVERY_PROVIDER=test_fixture selects the synthetic test "
            "provider, which only runs when "
            "JOB_DISCOVERY_ENABLE_TEST_PROVIDER=true is also set. It must "
            "never be enabled in production.",
            status_code=503,
        )


class JobDiscoveryUnknownProviderError(JobDiscoveryServiceError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            f"Unknown JOB_DISCOVERY_PROVIDER '{provider}'. Supported values: "
            f"{', '.join(sorted(SUPPORTED_PROVIDERS))}.",
            status_code=503,
        )


class JobDiscoveryAlreadyRunningError(JobDiscoveryServiceError):
    def __init__(self) -> None:
        super().__init__(
            "A discovery run is already in progress. Try again once it "
            "finishes.",
            status_code=409,
        )


# Guards run_configured_discovery against overlapping executions (e.g. the
# scheduler firing while an operator's manual trigger is still in flight).
# A plain in-process threading.Lock is enough - and *only* enough - because
# the api container runs a single uvicorn worker process (see the
# Dockerfile: no --workers flag) with sync path operations dispatched to a
# thread pool within that one process, not across multiple processes or
# containers. If this deployment is ever scaled to multiple worker
# processes/containers, this must become a DB-level lock (e.g. Postgres
# advisory locks) instead - do not reach for distributed locking
# infrastructure (Redis, etc.) before that is actually true.
_discovery_lock = threading.Lock()


PROVIDER_GREENHOUSE = "greenhouse"
PROVIDER_TEST_FIXTURE = "test_fixture"
SUPPORTED_PROVIDERS = {PROVIDER_GREENHOUSE, PROVIDER_TEST_FIXTURE}


@dataclass
class DiscoveryRunSummary:
    """Deterministic operational counters for one run (not AI metrics).

    fetched = normalized + normalization rejections
    normalized = accepted + validation rejections + duplicates
    accepted = inserted + updated
    """

    source: str
    is_test_data: bool
    fetched: int
    normalized: int
    accepted: int
    rejected: int
    duplicates: int
    inserted: int
    updated: int
    rejected_reasons: list[str]


def _configured_provider() -> str | None:
    value = (settings.job_discovery_provider or "").strip().lower()
    return value or None


def is_test_provider_enabled() -> bool:
    """True only when an operator explicitly turned test mode on. Also
    gates whether fixture jobs are visible at all (job_access.py)."""
    return bool(settings.job_discovery_enable_test_provider)


def build_configured_source() -> JobSourceAdapter:
    """Build the source adapter from configuration.

    This is the single place a provider is chosen, so the router/service
    boundary never needs to know which concrete adapter is in use. Adding
    an approved real provider means one more branch here plus its adapter.

    - unset / "greenhouse": Greenhouse, if its board settings are present
      (the pre-AJI-024 behavior), else JobDiscoveryNotConfiguredError.
    - "test_fixture": the synthetic fixture provider, only when
      JOB_DISCOVERY_ENABLE_TEST_PROVIDER is true.
    - anything else: JobDiscoveryUnknownProviderError - never a fallback.
    """
    provider = _configured_provider()

    if provider == PROVIDER_TEST_FIXTURE:
        if not is_test_provider_enabled():
            raise JobDiscoveryTestProviderDisabledError()

        return TestFixtureJobSource()

    if provider not in (None, PROVIDER_GREENHOUSE):
        raise JobDiscoveryUnknownProviderError(provider)

    board_token = settings.job_discovery_greenhouse_board_token
    company_name = settings.job_discovery_greenhouse_company_name

    if not board_token or not company_name:
        raise JobDiscoveryNotConfiguredError()

    return GreenhouseJobSource(
        board_token=board_token,
        company_name=company_name,
    )


def run_configured_discovery(db: Session) -> DiscoveryRunSummary:
    """Fetch from the configured source and run it through the existing
    discovery pipeline, committing on success.

    Never fabricates jobs: if no source is configured, or the source
    cannot be reached, this raises rather than returning a fake/empty
    success.

    Records one DiscoveryRun row for observability (source, start/end
    time, status, counts, safe error info) - whether the run succeeds or
    fails. A run that never starts (e.g. no source configured, or one is
    already in progress) has nothing to record, since no attempt was made.

    Rejects with JobDiscoveryAlreadyRunningError (409) rather than
    running concurrently with another in-flight call - see
    `_discovery_lock` for why a plain in-process lock is sufficient here.
    """
    source = build_configured_source()

    if not _discovery_lock.acquire(blocking=False):
        raise JobDiscoveryAlreadyRunningError()

    try:
        run = DiscoveryRun(
            id=uuid.uuid4(), source=source.source_name, status="running"
        )
        db.add(run)

        try:
            raw_jobs = source.fetch_raw_jobs()
        except JobSourceFetchError as exc:
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            run.error_message = str(exc)[:_ERROR_MESSAGE_MAX_LEN]
            db.commit()
            raise JobDiscoveryServiceError(
                f"Unable to fetch jobs from {source.source_name}: {exc}",
                status_code=502,
            ) from exc

        try:
            normalized_jobs, normalization_errors = normalize_raw_jobs(
                source, raw_jobs
            )
            result: PipelineResult = run_discovery_pipeline(
                db, normalized_jobs
            )
            outcome = SourceDiscoveryResult(
                source=source.source_name,
                is_test_provider=bool(source.is_test_provider),
                fetched=len(raw_jobs),
                normalization_errors=normalization_errors,
                pipeline=result,
            )

            run.status = "succeeded"
            run.completed_at = datetime.utcnow()
            run.fetched_count = outcome.fetched
            run.normalized_count = outcome.normalized
            run.inserted_count = outcome.inserted
            run.updated_count = outcome.updated
            run.rejected_count = outcome.rejected
            run.duplicate_count = outcome.duplicates

            db.commit()
        except Exception as exc:  # noqa: BLE001 - e.g. a DB outage mid-run
            # A failure here (including in db.commit() itself) means the
            # DiscoveryRun "running" row never got committed either, so
            # there is nothing to update in place. Not attempting a
            # second write in the same broken transaction is deliberate:
            # the caller (the request's get_db dependency) rolls the
            # session back on close, and this failure mode is rare enough
            # that losing the run's own observability row is an
            # acceptable trade-off against the risk of a second write
            # compounding a real DB outage.
            logger.error(
                "Discovery run for %s failed: %s", source.source_name, exc
            )
            raise JobDiscoveryServiceError(
                f"Job discovery run failed while persisting results: {exc}",
                status_code=503,
            ) from exc
    finally:
        _discovery_lock.release()

    return DiscoveryRunSummary(
        source=outcome.source,
        is_test_data=outcome.is_test_provider,
        fetched=outcome.fetched,
        normalized=outcome.normalized,
        accepted=outcome.accepted,
        rejected=outcome.rejected,
        duplicates=outcome.duplicates,
        inserted=outcome.inserted,
        updated=outcome.updated,
        rejected_reasons=outcome.rejected_reasons,
    )


@dataclass
class DiscoveryStatus:
    source_configured: bool
    test_mode: bool
    last_run_status: str | None
    last_run_completed_at: datetime | None


def get_discovery_status(db: Session) -> DiscoveryStatus:
    """User-safe discovery state for the Jobs UI: whether any source is
    configured, whether test mode is on, and how the latest run ended.
    Never includes configuration values or error text."""
    try:
        build_configured_source()
        source_configured = True
    except JobDiscoveryServiceError:
        source_configured = False

    query = db.query(DiscoveryRun)

    if not is_test_provider_enabled():
        query = query.filter(DiscoveryRun.source != TEST_FIXTURE_SOURCE)

    last_run = query.order_by(DiscoveryRun.started_at.desc()).first()

    return DiscoveryStatus(
        source_configured=source_configured,
        test_mode=is_test_provider_enabled(),
        last_run_status=last_run.status if last_run else None,
        last_run_completed_at=last_run.completed_at if last_run else None,
    )
