from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from apps.api.models import Job
from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.persistence import upsert_discovered_job
from services.job_discovery.validator import JobValidationError


@dataclass
class JobIngestionError:
    job: DiscoveredJob
    reason: str


@dataclass
class PipelineResult:
    inserted: list[Job] = field(default_factory=list)
    updated: list[Job] = field(default_factory=list)
    rejected: list[JobIngestionError] = field(default_factory=list)

    @property
    def accepted(self) -> list[Job]:
        return [*self.inserted, *self.updated]


def run_discovery_pipeline(
    db: Session,
    discovered_jobs: list[DiscoveredJob],
) -> PipelineResult:
    """
    Push a batch of discovered jobs through validation, deduplication, and
    persistence (normalization is expected to already be applied by the
    source adapter that produced each DiscoveredJob).

    A single bad job is recorded as rejected and does not stop the batch.
    Changes are flushed but left uncommitted; the caller owns the
    transaction boundary and should call db.commit() once satisfied.
    """
    result = PipelineResult()

    for discovered_job in discovered_jobs:
        try:
            with db.begin_nested():
                job = upsert_discovered_job(db, discovered_job)
        except JobValidationError as exc:
            result.rejected.append(
                JobIngestionError(job=discovered_job, reason=str(exc))
            )
            continue
        except Exception as exc:  # noqa: BLE001 - isolate unexpected per-job failures
            result.rejected.append(
                JobIngestionError(
                    job=discovered_job,
                    reason=f"Unexpected error: {exc}",
                )
            )
            continue

        if job.first_seen_at == job.last_seen_at:
            result.inserted.append(job)
        else:
            result.updated.append(job)

    return result
