from __future__ import annotations

from typing import Protocol

from services.job_discovery.contracts import DiscoveredJob


class JobSourceAdapter(Protocol):
    """A source adapter fetches postings from one external provider and
    maps them into DiscoveredJob objects, ready for the discovery pipeline
    (validation, deduplication, persistence)."""

    source_name: str

    def fetch_jobs(self) -> list[DiscoveredJob]:
        ...
