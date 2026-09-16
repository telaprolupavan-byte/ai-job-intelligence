from __future__ import annotations

import hashlib

from services.job_discovery.contracts import DiscoveredJob


def normalize_identity_text(value: str | None) -> str:
    if not value:
        return ""

    return " ".join(value.lower().split())


def build_job_fingerprint(job: DiscoveredJob) -> str:
    """
    Build a deterministic identity for a discovered job.

    Prefer the source-provided job ID when available.
    Otherwise fall back to stable job attributes.
    """

    if job.source_job_id:
        identity = (
            f"{normalize_identity_text(job.source)}:"
            f"{normalize_identity_text(job.source_job_id)}"
        )
    else:
        identity = "|".join(
            [
                normalize_identity_text(job.source),
                normalize_identity_text(job.company),
                normalize_identity_text(job.title),
                normalize_identity_text(job.location),
                normalize_identity_text(job.application_url),
            ]
        )

    return hashlib.sha256(identity.encode("utf-8")).hexdigest()