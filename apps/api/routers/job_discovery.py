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

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.database import get_db
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
    try:
        summary = run_configured_discovery(db)
    except JobDiscoveryServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    logger.info(
        "Job discovery run: source=%s fetched=%d inserted=%d updated=%d rejected=%d",
        summary.source,
        summary.fetched,
        summary.inserted,
        summary.updated,
        summary.rejected,
    )

    return {
        "source": summary.source,
        "fetched": summary.fetched,
        "inserted": summary.inserted,
        "updated": summary.updated,
        "rejected": summary.rejected,
        "rejected_reasons": summary.rejected_reasons,
    }
