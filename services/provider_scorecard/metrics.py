from __future__ import annotations

from services.job_discovery.contracts import DiscoveredJob

# The fields measured for completeness. Salary fields are deliberately
# excluded - most providers legitimately never disclose salary, so a low
# salary-completeness rate would penalize a provider for something outside
# its control rather than measuring data quality.
COMPLETENESS_FIELDS = (
    "title",
    "company",
    "description",
    "location",
    "remote_type",
    "employment_type",
    "source_url",
    "application_url",
    "posted_at",
)


def compute_field_completeness(
    jobs: list[DiscoveredJob],
    fields: tuple[str, ...] = COMPLETENESS_FIELDS,
) -> dict[str, float]:
    """Fraction of ``jobs`` with a non-empty value for each of ``fields``."""

    if not jobs:
        return {field_name: 0.0 for field_name in fields}

    return {
        field_name: sum(1 for job in jobs if _has_value(getattr(job, field_name)))
        / len(jobs)
        for field_name in fields
    }


def _has_value(value) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def compute_rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0

    return count / total
