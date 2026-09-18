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
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
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


@dataclass
class DiscoveryRunSummary:
    source: str
    fetched: int
    inserted: int
    updated: int
    rejected: int
    rejected_reasons: list[str]


def build_configured_source() -> JobSourceAdapter:
    """Build the source adapter from configuration.

    Raises JobDiscoveryNotConfiguredError if no source is configured. Only
    one provider (Greenhouse) is wired up today; this function is the
    single place a second provider would be added, so the router/service
    boundary never needs to know which concrete adapter is in use.
    """
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
    fails. A run that never starts (e.g. no source configured) has
    nothing to record, since no attempt was made.
    """
    source = build_configured_source()

    run = DiscoveryRun(id=uuid.uuid4(), source=source.source_name, status="running")
    db.add(run)

    try:
        discovered_jobs = source.fetch_jobs()
    except GreenhouseAdapterError as exc:
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.error_message = str(exc)[:_ERROR_MESSAGE_MAX_LEN]
        db.commit()
        raise JobDiscoveryServiceError(
            f"Unable to fetch jobs from {source.source_name}: {exc}",
            status_code=502,
        ) from exc

    try:
        result: PipelineResult = run_discovery_pipeline(db, discovered_jobs)

        run.status = "succeeded"
        run.completed_at = datetime.utcnow()
        run.fetched_count = len(discovered_jobs)
        run.inserted_count = len(result.inserted)
        run.updated_count = len(result.updated)
        run.rejected_count = len(result.rejected)

        db.commit()
    except Exception as exc:  # noqa: BLE001 - e.g. a DB outage mid-run
        # A failure here (including in db.commit() itself) means the
        # DiscoveryRun "running" row never got committed either, so there
        # is nothing to update in place. Not attempting a second write in
        # the same broken transaction is deliberate: the caller (the
        # request's get_db dependency) rolls the session back on close,
        # and this failure mode is rare enough that losing the run's own
        # observability row is an acceptable trade-off against the risk
        # of a second write compounding a real DB outage.
        logger.error("Discovery run for %s failed: %s", source.source_name, exc)
        raise JobDiscoveryServiceError(
            f"Job discovery run failed while persisting results: {exc}",
            status_code=503,
        ) from exc

    return DiscoveryRunSummary(
        source=source.source_name,
        fetched=len(discovered_jobs),
        inserted=len(result.inserted),
        updated=len(result.updated),
        rejected=len(result.rejected),
        rejected_reasons=[item.reason for item in result.rejected],
    )
