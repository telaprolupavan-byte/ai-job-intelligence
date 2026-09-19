"""Operational trigger for the Job Discovery pipeline.

This is a system-to-system endpoint (meant to be called by an external
scheduler - cron, a platform's scheduled task feature, a scheduled CI
workflow), not a user-facing one: there is no admin/role concept on
`User` to gate it with, so it is instead gated by a shared secret
(`settings.job_discovery_trigger_token`) that only whoever configures the
scheduler knows. See services/job_discovery/README.md for how to point
this at a real source.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.models import DiscoveryRun
from apps.api.services.job_discovery_service import (
    JobDiscoveryServiceError,
    run_configured_discovery,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal/job-discovery",
    tags=["Job Discovery (internal)"],
)


def _verify_trigger_token(
    x_discovery_trigger_token: str | None = Header(default=None),
) -> None:
    configured_token = settings.job_discovery_trigger_token

    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Job discovery trigger is disabled: "
                "JOB_DISCOVERY_TRIGGER_TOKEN is not configured."
            ),
        )

    if (
        not x_discovery_trigger_token
        or x_discovery_trigger_token != configured_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing discovery trigger token.",
        )


@router.post(
    "/run",
    dependencies=[Depends(_verify_trigger_token)],
)
def trigger_job_discovery(db: Session = Depends(get_db)):
    """Runs every independently-configured source (Greenhouse, TheirStack)
    once each and returns one summary per source. A given source failing
    to fetch is reported in its own entry (status="failed") rather than
    failing the whole request - see run_configured_discovery."""
    try:
        summaries = run_configured_discovery(db)
    except JobDiscoveryServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    for summary in summaries:
        logger.info(
            "Job discovery run: source=%s status=%s fetched=%d inserted=%d "
            "updated=%d rejected=%d",
            summary.source,
            summary.status,
            summary.fetched,
            summary.inserted,
            summary.updated,
            summary.rejected,
        )

    return {
        "runs": [
            {
                "source": summary.source,
                "status": summary.status,
                "fetched": summary.fetched,
                "inserted": summary.inserted,
                "updated": summary.updated,
                "rejected": summary.rejected,
                "rejected_reasons": summary.rejected_reasons,
                "error": summary.error,
            }
            for summary in summaries
        ]
    }


@router.get(
    "/runs",
    dependencies=[Depends(_verify_trigger_token)],
)
def list_discovery_runs(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Recent Discovery Run history, most recent first - the observability
    surface for whatever calls POST /run on a schedule."""
    runs = db.execute(
        select(DiscoveryRun)
        .order_by(DiscoveryRun.started_at.desc())
        .limit(limit)
    ).scalars().all()

    return [
        {
            "id": str(run.id),
            "source": run.source,
            "status": run.status,
            "started_at": run.started_at.isoformat(),
            "completed_at": (
                run.completed_at.isoformat() if run.completed_at else None
            ),
            "fetched": run.fetched_count,
            "inserted": run.inserted_count,
            "updated": run.updated_count,
            "rejected": run.rejected_count,
            "error_message": run.error_message,
        }
        for run in runs
    ]
