from __future__ import annotations

import dataclasses

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
    normalize_text,
    normalize_url,
)


def normalize_candidate_job(job: DiscoveredJob) -> DiscoveredJob:
    """
    Apply ``services.job_discovery.normalizer``'s field-level normalization
    to a raw candidate job, the same normalization every real source
    adapter (e.g. Greenhouse) already applies before a job reaches the
    discovery pipeline. Reused here rather than reimplemented so "does this
    provider's raw data normalize cleanly" measures the same rules
    production discovery would apply.
    """

    return dataclasses.replace(
        job,
        title=normalize_text(job.title) or job.title,
        company=normalize_text(job.company) or job.company,
        description=normalize_text(job.description),
        requirements=normalize_text(job.requirements),
        responsibilities=normalize_text(job.responsibilities),
        location=normalize_text(job.location),
        remote_type=normalize_remote_type(job.remote_type),
        employment_type=normalize_employment_type(job.employment_type),
        source_url=normalize_url(job.source_url),
        application_url=normalize_url(job.application_url),
    )
