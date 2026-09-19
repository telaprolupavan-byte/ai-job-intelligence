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
`build_configured_sources` simply omits Greenhouse until an operator
configures them.

AJI-021 adds TheirStack as a second, independently-enabled source
alongside Greenhouse (`settings.theirstack_enabled` +
`settings.theirstack_api_key`). One discovery run now fetches from every
configured source in turn, records one `DiscoveryRun` row per source (so
each provider's success/failure/counts stay independently observable),
and a failure fetching from one source never prevents another configured
source from running - that independence is the whole point of "enabled
independently".
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import DiscoveryRun
from services.job_discovery.pipeline import PipelineResult, run_discovery_pipeline
from services.job_discovery.sources.base import JobSourceAdapter
from services.job_discovery.sources.greenhouse import (
    GreenhouseAdapterError,
    GreenhouseJobSource,
)
from services.job_discovery.sources.theirstack import (
    TheirStackAdapterError,
    TheirStackJobSource,
)


logger = logging.getLogger(__name__)

# String column limit on DiscoveryRun.error_message - truncate so an
# unusually long exception message can never fail that write too.
_ERROR_MESSAGE_MAX_LEN = 1000

# Exception types raised by a source adapter's fetch_jobs() that this
# service treats as "that provider's fetch failed" (recorded as a failed
# DiscoveryRun for that source alone) rather than a systemic failure.
_SOURCE_FETCH_ERRORS = (GreenhouseAdapterError, TheirStackAdapterError)


class JobDiscoveryServiceError(Exception):
    def __init__(self, message: str, *, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class JobDiscoveryNotConfiguredError(JobDiscoveryServiceError):
    def __init__(self) -> None:
        super().__init__(
            "Job discovery has no configured source. Set "
            "JOB_DISCOVERY_GREENHOUSE_BOARD_TOKEN and "
            "JOB_DISCOVERY_GREENHOUSE_COMPANY_NAME, and/or "
            "THEIRSTACK_ENABLED=true with THEIRSTACK_API_KEY, to enable it.",
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


@dataclass
class DiscoveryRunSummary:
    source: str
    status: str  # "succeeded" | "failed"
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    rejected_reasons: list[str] = field(default_factory=list)
    error: str | None = None


def _build_theirstack_source() -> TheirStackJobSource:
    job_titles = (
        [
            title.strip()
            for title in settings.theirstack_job_titles.split(",")
            if title.strip()
        ]
        if settings.theirstack_job_titles
        else None
    )
    country_codes = [
        code.strip()
        for code in settings.theirstack_country_codes.split(",")
        if code.strip()
    ] or None

    return TheirStackJobSource(
        api_key=settings.theirstack_api_key,
        job_title_or=job_titles,
        job_country_code_or=country_codes,
        posted_at_max_age_days=settings.theirstack_posted_at_max_age_days,
        max_results=settings.theirstack_max_results,
        page_size=settings.theirstack_page_size,
        request_timeout=settings.theirstack_timeout_seconds,
        max_retries=settings.theirstack_max_retries,
    )


def build_configured_sources() -> list[JobSourceAdapter]:
    """Build every source adapter enabled by configuration.

    Each provider is independent: Greenhouse is included iff its board
    token/company name are both set; TheirStack is included iff
    THEIRSTACK_ENABLED is true (a misconfiguration - enabled without an
    API key - is logged and that provider is simply omitted, rather than
    blocking Greenhouse from running). Raises
    JobDiscoveryNotConfiguredError only if the resulting list is empty -
    no provider is configured at all.
    """
    sources: list[JobSourceAdapter] = []

    board_token = settings.job_discovery_greenhouse_board_token
    company_name = settings.job_discovery_greenhouse_company_name

    if board_token and company_name:
        sources.append(
            GreenhouseJobSource(
                board_token=board_token,
                company_name=company_name,
            )
        )

    if settings.theirstack_enabled:
        if not settings.theirstack_api_key:
            logger.warning(
                "THEIRSTACK_ENABLED is true but THEIRSTACK_API_KEY is not "
                "set - skipping TheirStack for this discovery run."
            )
        else:
            sources.append(_build_theirstack_source())

    if not sources:
        raise JobDiscoveryNotConfiguredError()

    return sources


def build_configured_source() -> JobSourceAdapter:
    """Backward-compatible single-source accessor: the first configured
    source, preferring Greenhouse. Prefer `build_configured_sources` for
    new code - this exists only for callers that genuinely need exactly
    one adapter."""
    return build_configured_sources()[0]


def _run_single_source(db: Session, source: JobSourceAdapter) -> DiscoveryRunSummary:
    """Fetch and persist one source's jobs. Flushes (via
    run_discovery_pipeline's per-job `db.begin_nested()`/`db.flush()`
    calls) but never commits - see run_configured_discovery, which
    commits once for the whole multi-source run, matching
    run_discovery_pipeline's own documented contract ("the caller owns
    the transaction boundary and should call db.commit() once
    satisfied"). A source's own fetch failure is caught here and recorded
    on its DiscoveryRun without raising, so it can't prevent another
    configured source from running; a failure inside the pipeline itself
    (e.g. a DB outage) is a systemic problem and is left to propagate."""
    run = DiscoveryRun(
        id=uuid.uuid4(),
        source=source.source_name,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(run)

    try:
        discovered_jobs = source.fetch_jobs()
    except _SOURCE_FETCH_ERRORS as exc:
        error_message = str(exc)[:_ERROR_MESSAGE_MAX_LEN]
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.error_message = error_message

        logger.warning(
            "Discovery fetch failed for %s: %s", source.source_name, error_message
        )

        return DiscoveryRunSummary(
            source=source.source_name,
            status="failed",
            error=error_message,
        )

    result: PipelineResult = run_discovery_pipeline(db, discovered_jobs)

    run.status = "succeeded"
    run.completed_at = datetime.utcnow()
    run.fetched_count = len(discovered_jobs)
    run.inserted_count = len(result.inserted)
    run.updated_count = len(result.updated)
    run.rejected_count = len(result.rejected)

    return DiscoveryRunSummary(
        source=source.source_name,
        status="succeeded",
        fetched=len(discovered_jobs),
        inserted=len(result.inserted),
        updated=len(result.updated),
        rejected=len(result.rejected),
        rejected_reasons=[item.reason for item in result.rejected],
    )


def run_configured_discovery(db: Session) -> list[DiscoveryRunSummary]:
    """Fetch from every configured source and run each through the
    existing discovery pipeline, committing once for the whole run.

    Never fabricates jobs: if no source is configured, this raises rather
    than returning a fake/empty success. A source that cannot be reached
    is recorded as a failed DiscoveryRun and reported in the returned
    list - it does not prevent other configured sources from running,
    since providers are enabled independently of one another. A failure
    while persisting (e.g. a DB outage) is systemic rather than specific
    to one provider, so - unlike a source fetch failure - it aborts the
    whole run (nothing from this run is committed) rather than being
    isolated to one provider.

    Rejects with JobDiscoveryAlreadyRunningError (409) rather than running
    concurrently with another in-flight call - see `_discovery_lock` for
    why a plain in-process lock is sufficient here.
    """
    sources = build_configured_sources()

    if not _discovery_lock.acquire(blocking=False):
        raise JobDiscoveryAlreadyRunningError()

    try:
        try:
            summaries = [_run_single_source(db, source) for source in sources]
            db.commit()
        except Exception as exc:  # noqa: BLE001 - e.g. a DB outage mid-run
            logger.error("Discovery run failed while persisting results: %s", exc)
            raise JobDiscoveryServiceError(
                f"Job discovery run failed while persisting results: {exc}",
                status_code=503,
            ) from exc

        return summaries
    finally:
        _discovery_lock.release()
