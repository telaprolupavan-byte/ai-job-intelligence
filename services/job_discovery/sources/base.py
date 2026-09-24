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

    AJI-028 contract additions for new adapters (existing adapters keep
    their behavior):

    - Network access goes through `services.job_discovery.source_http`
      (`SourceHttpClient` with an `HttpPolicy` derived from the provider's
      documented rate limit): bounded timeout, retry/backoff for
      transient failures, `Retry-After`, response-size cap, throttle.
    - A paged provider is read with
      `services.job_discovery.pagination.fetch_bounded_pages` - newest
      first, at most `MAX_PAGES_PER_RUN` pages per run.
    - `normalize_raw_job` sets `expires_at` only from an expiry/closing
      date the provider actually states. It never derives one, and
      nothing infers a closed posting from its absence in a fetch.
    - A source whose terms require crediting it registers a
      `SourceAttribution` in `services.job_discovery.attribution` under
      its `source_name`; every non-test provider must be registered.
    - Only a source whose automated access and use are permitted for
      NERO's use case may be implemented at all: publicly visible is not
      the same as permitted.
    """

    source_name: str
    is_test_provider: bool

    def fetch_raw_jobs(self) -> list[RawProviderJob]:
        ...

    def normalize_raw_job(self, raw_job: RawProviderJob) -> DiscoveredJob:
        ...
