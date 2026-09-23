from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from apps.api.models import Job
from services.job_discovery.contracts import DiscoveredJob, RawProviderJob
from services.job_discovery.deduplicator import build_job_fingerprint
from services.job_discovery.persistence import upsert_discovered_job
from services.job_discovery.sources.base import JobSourceAdapter
from services.job_discovery.validator import (
    JobValidationError,
    validate_discovered_job,
)


@dataclass
class JobIngestionError:
    job: DiscoveredJob
    reason: str


@dataclass
class NormalizationError:
    raw_job: RawProviderJob
    reason: str


@dataclass
class PipelineResult:
    inserted: list[Job] = field(default_factory=list)
    updated: list[Job] = field(default_factory=list)
    rejected: list[JobIngestionError] = field(default_factory=list)
    # Records whose identity (see build_job_fingerprint) already appeared
    # earlier in the same batch. Not persisted a second time.
    duplicates: list[DiscoveredJob] = field(default_factory=list)

    @property
    def accepted(self) -> list[Job]:
        return [*self.inserted, *self.updated]


@dataclass
class SourceDiscoveryResult:
    """Deterministic operational counters for one provider run (AJI-024).

    fetched     = raw records the provider returned
    normalized  = fetched - normalization rejections
    rejected    = normalization rejections + validation/persistence rejections
    duplicates  = valid records repeating an identity earlier in the batch
    accepted    = inserted + updated
    """

    source: str
    is_test_provider: bool
    fetched: int
    normalization_errors: list[NormalizationError]
    pipeline: PipelineResult

    @property
    def normalized(self) -> int:
        return self.fetched - len(self.normalization_errors)

    @property
    def inserted(self) -> int:
        return len(self.pipeline.inserted)

    @property
    def updated(self) -> int:
        return len(self.pipeline.updated)

    @property
    def accepted(self) -> int:
        return len(self.pipeline.accepted)

    @property
    def duplicates(self) -> int:
        return len(self.pipeline.duplicates)

    @property
    def rejected(self) -> int:
        return len(self.normalization_errors) + len(self.pipeline.rejected)

    @property
    def rejected_reasons(self) -> list[str]:
        return [
            *(error.reason for error in self.normalization_errors),
            *(error.reason for error in self.pipeline.rejected),
        ]


def run_discovery_pipeline(
    db: Session,
    discovered_jobs: list[DiscoveredJob],
) -> PipelineResult:
    """
    Push a batch of normalized jobs through validation, deduplication, and
    persistence.

    A single bad job is recorded as rejected and does not stop the batch.
    A job whose identity already appeared earlier in the batch is counted
    as a duplicate and not written again. Changes are flushed but left
    uncommitted; the caller owns the transaction boundary and should call
    db.commit() once satisfied.
    """
    result = PipelineResult()
    seen_identities: set[str] = set()

    for discovered_job in discovered_jobs:
        try:
            validate_discovered_job(discovered_job)
        except JobValidationError as exc:
            result.rejected.append(
                JobIngestionError(job=discovered_job, reason=str(exc))
            )
            continue

        identity = build_job_fingerprint(discovered_job)

        if identity in seen_identities:
            result.duplicates.append(discovered_job)
            continue

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

        seen_identities.add(identity)

        if job.first_seen_at == job.last_seen_at:
            result.inserted.append(job)
        else:
            result.updated.append(job)

    return result


def normalize_raw_jobs(
    source: JobSourceAdapter,
    raw_jobs: list[RawProviderJob],
) -> tuple[list[DiscoveredJob], list[NormalizationError]]:
    """Run the adapter's deterministic normalization per record, so one
    malformed provider record is a rejection, never a failed run."""
    normalized: list[DiscoveredJob] = []
    errors: list[NormalizationError] = []

    for raw_job in raw_jobs:
        try:
            normalized.append(source.normalize_raw_job(raw_job))
        except Exception as exc:  # noqa: BLE001 - one bad record must not stop the batch
            errors.append(
                NormalizationError(
                    raw_job=raw_job,
                    reason=f"Normalization failed: {exc}",
                )
            )

    return normalized, errors

