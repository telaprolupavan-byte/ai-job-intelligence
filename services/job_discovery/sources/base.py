from __future__ import annotations

from typing import Protocol

from services.job_discovery.contracts import DiscoveredJob, RawProviderJob


class JobSourceFetchError(RuntimeError):
    """A provider could not be read at all (network, HTTP status, bad
    response shape). Per-record problems are never raised as this - they
    surface as a normalization rejection for that one record instead."""


class JobSourceAdapter(Protocol):
    """The provider boundary (AJI-024).

    ```
    Provider -> fetch_raw_jobs() -> RawProviderJob
             -> normalize_raw_job() -> DiscoveredJob (canonical)
             -> validate -> deduplicate -> persist   (shared, provider-free)
    ```

    Everything provider-specific lives behind these two methods; the
    pipeline, persistence, API and UI never branch on which provider is in
    use. `normalize_raw_job` must be deterministic (same raw record -> same
    DiscoveredJob), must never invent a value the provider did not supply,
    and may raise on a malformed record - the pipeline records that one
    record as rejected and carries on with the rest of the batch.

    `is_test_provider` marks deterministic fixture providers. The
    orchestration layer refuses to run one unless test mode is explicitly
    enabled (see apps/api/services/job_discovery_service.py).
    """

    source_name: str
    is_test_provider: bool

    def fetch_raw_jobs(self) -> list[RawProviderJob]:
        ...

    def normalize_raw_job(self, raw_job: RawProviderJob) -> DiscoveredJob:
        ...
