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

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import DiscoveryRun, User
from apps.api.services.job_discovery_service import (
    JobDiscoveryServiceError,
    get_discovery_status,
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

    # Constant-time comparison so response timing never leaks how much of
    # a guessed token matched.
    if not x_discovery_trigger_token or not hmac.compare_digest(
        x_discovery_trigger_token.encode("utf-8"),
        configured_token.encode("utf-8"),
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
    try:
        summary = run_configured_discovery(db)
    except JobDiscoveryServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    logger.info(
        "Job discovery run: source=%s test_data=%s fetched=%d normalized=%d "
        "accepted=%d rejected=%d duplicates=%d inserted=%d updated=%d",
        summary.source,
        summary.is_test_data,
        summary.fetched,
        summary.normalized,
        summary.accepted,
        summary.rejected,
        summary.duplicates,
        summary.inserted,
        summary.updated,
    )

    # Deterministic operational counters (AJI-024) - not AI metrics.
    return {
        "source": summary.source,
        "is_test_data": summary.is_test_data,
        "fetched": summary.fetched,
        "normalized": summary.normalized,
        "accepted": summary.accepted,
        "rejected": summary.rejected,
        "duplicates": summary.duplicates,
        "inserted": summary.inserted,
        "updated": summary.updated,
        "rejected_reasons": summary.rejected_reasons,
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
            "normalized": run.normalized_count,
            "accepted": run.inserted_count + run.updated_count,
            "rejected": run.rejected_count,
            "duplicates": run.duplicate_count,
            "inserted": run.inserted_count,
            "updated": run.updated_count,
            "error_message": run.error_message,
        }
        for run in runs
    ]


# User-facing, read-only discovery state for the Jobs UI (AJI-024). Lives
# outside the /internal prefix and uses normal user auth - it can never
# run discovery, and it exposes no configuration values, provider
# credentials, or run error text.
status_router = APIRouter(
    prefix="/job-discovery",
    tags=["Job Discovery"],
)


@status_router.get("/status")
def read_discovery_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    discovery_status = get_discovery_status(db)

    return {
        "source_configured": discovery_status.source_configured,
        "test_mode": discovery_status.test_mode,
        "last_run": (
            {
                "status": discovery_status.last_run_status,
                "completed_at": (
                    discovery_status.last_run_completed_at.isoformat()
                    if discovery_status.last_run_completed_at
                    else None
                ),
            }
            if discovery_status.last_run_status
            else None
        ),
    }
