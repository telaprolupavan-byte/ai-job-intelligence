from __future__ import annotations

import statistics
from datetime import datetime, timezone

from services.job_discovery.contracts import DiscoveredJob

# A keyword heuristic, not an authoritative taxonomy - the same
# "directionally indicative, not a ground truth" caveat every other
# keyword-based signal in this codebase carries (e.g.
# services/eligibility/job_signals.py's phrase matching). Matches against
# title + description (already-normalized text - whitespace-collapsed,
# original casing), case-insensitively.
AI_ML_KEYWORDS = (
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "natural language processing",
    "nlp",
    "computer vision",
    "data scientist",
    "data science",
    "ml engineer",
    "mlops",
    "ml ops",
    "ai engineer",
    "ai researcher",
    "ai research",
    "large language model",
    " llm",
    "neural network",
    "generative ai",
)


def is_ai_ml_job(job: DiscoveredJob) -> bool:
    haystack = " ".join(filter(None, [job.title, job.description])).lower()

    return any(keyword in haystack for keyword in AI_ML_KEYWORDS)


def count_ai_ml_jobs(jobs: list[DiscoveredJob]) -> int:
    return sum(1 for job in jobs if is_ai_ml_job(job))


def count_by_employment_type(jobs: list[DiscoveredJob], employment_type: str) -> int:
    """``jobs`` must already be normalized - compares against the
    normalizer's canonical value (e.g. "full_time", "contract")."""

    return sum(1 for job in jobs if job.employment_type == employment_type)


def count_remote_jobs(jobs: list[DiscoveredJob]) -> int:
    """``jobs`` must already be normalized - compares against the
    normalizer's canonical "remote" value."""

    return sum(1 for job in jobs if job.remote_type == "remote")


def count_with_salary(jobs: list[DiscoveredJob]) -> int:
    return sum(1 for job in jobs if job.salary_min is not None or job.salary_max is not None)


def count_with_application_url(jobs: list[DiscoveredJob]) -> int:
    return sum(1 for job in jobs if job.application_url)


def compute_median_freshness_days(
    jobs: list[DiscoveredJob],
    *,
    reference_date: datetime | None = None,
) -> float | None:
    """
    Median age, in days, of postings that have a ``posted_at`` value.
    Returns ``None`` when no job in ``jobs`` has one - never fabricated as
    0 (which would misleadingly read as "posted today").

    Dates are compared as calendar dates (``.date()``), not exact
    timestamps, since providers disclose posting dates at very different
    precisions (Adzuna/The Muse: full ISO timestamps; USAJOBS: date-only)
    and mixing aware/naive datetimes across providers would otherwise
    raise rather than produce a comparable number.
    """

    reference = (reference_date or datetime.now(timezone.utc)).date()

    ages = [
        (reference - job.posted_at.date()).days
        for job in jobs
        if job.posted_at is not None
    ]

    if not ages:
        return None

    return statistics.median(ages)
