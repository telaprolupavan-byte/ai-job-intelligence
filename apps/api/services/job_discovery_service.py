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

from dataclasses import dataclass

from sqlalchemy.orm import Session

from apps.api.config import settings
from services.job_discovery.pipeline import PipelineResult, run_discovery_pipeline
from services.job_discovery.sources.base import JobSourceAdapter
from services.job_discovery.sources.greenhouse import (
    GreenhouseAdapterError,
    GreenhouseJobSource,
)


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
    """
    source = build_configured_source()

    try:
        discovered_jobs = source.fetch_jobs()
    except GreenhouseAdapterError as exc:
        raise JobDiscoveryServiceError(
            f"Unable to fetch jobs from {source.source_name}: {exc}",
            status_code=502,
        ) from exc

    result: PipelineResult = run_discovery_pipeline(db, discovered_jobs)
    db.commit()

    return DiscoveryRunSummary(
        source=source.source_name,
        fetched=len(discovered_jobs),
        inserted=len(result.inserted),
        updated=len(result.updated),
        rejected=len(result.rejected),
        rejected_reasons=[item.reason for item in result.rejected],
    )
