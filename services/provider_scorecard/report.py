from __future__ import annotations

from dataclasses import dataclass, field

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.deduplicator import build_job_fingerprint
from services.job_discovery.validator import JobValidationError, validate_discovered_job
from services.provider_scorecard.metrics import compute_rate
from services.provider_scorecard.normalize import normalize_candidate_job
from services.provider_scorecard.report_metrics import (
    compute_median_freshness_days,
    count_ai_ml_jobs,
    count_by_employment_type,
    count_remote_jobs,
    count_with_application_url,
    count_with_salary,
)

# AJI-018C's exact requested row order - render_markdown_table follows
# this, not dict/insertion order, so the table always matches the ticket
# regardless of how ProviderReport's fields happen to be declared.
REPORT_ROWS = (
    "Raw jobs",
    "Valid jobs",
    "Unique jobs",
    "Duplicate %",
    "AI/ML jobs",
    "FT jobs",
    "Contract jobs",
    "Remote jobs",
    "Salary available",
    "Application URL",
    "Freshness",
    "API reliability",
)


@dataclass
class ProviderReport:
    """
    One provider's column in the AJI-018C comparison table. Deliberately
    has no score/rank/recommendation field of its own - see this module's
    docstring and services/provider_scorecard/README.md's "No automatic
    score or winner" section. A Product Owner reads these numbers side by
    side and decides; nothing here decides for them.
    """

    provider: str

    raw_jobs: int = 0
    valid_jobs: int = 0
    unique_jobs: int = 0
    duplicate_rate: float = 0.0
    ai_ml_jobs: int = 0
    ft_jobs: int = 0
    contract_jobs: int = 0
    remote_jobs: int = 0
    salary_available_rate: float = 0.0
    application_url_rate: float = 0.0
    freshness_days: float | None = None
    reliability_rate: float | None = None

    successful_scenarios: int = 0
    total_scenarios: int = 0
    scenario_errors: dict[str, str] = field(default_factory=dict)

    def as_row_values(self) -> dict[str, str]:
        return {
            "Raw jobs": str(self.raw_jobs),
            "Valid jobs": str(self.valid_jobs),
            "Unique jobs": str(self.unique_jobs),
            "Duplicate %": f"{self.duplicate_rate:.0%}",
            "AI/ML jobs": str(self.ai_ml_jobs),
            "FT jobs": str(self.ft_jobs),
            "Contract jobs": str(self.contract_jobs),
            "Remote jobs": str(self.remote_jobs),
            "Salary available": f"{self.salary_available_rate:.0%}",
            "Application URL": f"{self.application_url_rate:.0%}",
            "Freshness": (
                f"{self.freshness_days:.0f}d (median)"
                if self.freshness_days is not None
                else "N/A"
            ),
            "API reliability": (
                f"{self.reliability_rate:.0%} "
                f"({self.successful_scenarios}/{self.total_scenarios} requests)"
                if self.total_scenarios
                else "N/A (no attempts reported)"
            ),
        }


def build_provider_report(
    provider: str,
    raw_jobs_by_scenario: dict[str, list[DiscoveredJob]],
    *,
    errors_by_scenario: dict[str, str] | None = None,
) -> ProviderReport:
    """
    Build one provider's report row from already-fetched raw results.

    ``raw_jobs_by_scenario`` maps scenario_id -> the raw (un-normalized -
    see services/provider_scorecard/normalize.py) DiscoveredJobs parsed
    from that scenario's successful response. ``errors_by_scenario`` maps
    scenario_id -> what went wrong for a scenario that was actually
    attempted but failed (a real HTTP error, a rate limit, an
    unparseable response) - passing these in is what makes "API
    reliability" a real measurement instead of only ever reading 100%
    because failed attempts were silently left out.

    Deduplication and every job-content metric (AI/ML, FT/Contract,
    Remote, salary, application URL, freshness) are computed over the
    GLOBAL set of jobs across every scenario combined, not per scenario -
    the same posting surfacing under two different scenario searches
    should count once, not twice, in "Unique jobs" or "AI/ML jobs".
    """

    errors_by_scenario = errors_by_scenario or {}

    raw_jobs = [
        job for jobs in raw_jobs_by_scenario.values() for job in jobs
    ]
    normalized_jobs = [normalize_candidate_job(job) for job in raw_jobs]

    valid_jobs = [job for job in normalized_jobs if _is_valid(job)]

    unique_jobs = _deduplicate(normalized_jobs)

    total_scenarios = len(raw_jobs_by_scenario) + len(errors_by_scenario)
    successful_scenarios = len(raw_jobs_by_scenario)

    return ProviderReport(
        provider=provider,
        raw_jobs=len(normalized_jobs),
        valid_jobs=len(valid_jobs),
        unique_jobs=len(unique_jobs),
        duplicate_rate=compute_rate(
            len(normalized_jobs) - len(unique_jobs), len(normalized_jobs)
        ),
        ai_ml_jobs=count_ai_ml_jobs(unique_jobs),
        ft_jobs=count_by_employment_type(unique_jobs, "full_time"),
        contract_jobs=count_by_employment_type(unique_jobs, "contract"),
        remote_jobs=count_remote_jobs(unique_jobs),
        salary_available_rate=compute_rate(count_with_salary(unique_jobs), len(unique_jobs)),
        application_url_rate=compute_rate(
            count_with_application_url(unique_jobs), len(unique_jobs)
        ),
        freshness_days=compute_median_freshness_days(unique_jobs),
        reliability_rate=compute_rate(successful_scenarios, total_scenarios)
        if total_scenarios
        else None,
        successful_scenarios=successful_scenarios,
        total_scenarios=total_scenarios,
        scenario_errors=dict(errors_by_scenario),
    )


def _is_valid(job: DiscoveredJob) -> bool:
    try:
        validate_discovered_job(job)
    except JobValidationError:
        return False

    return True


def _deduplicate(jobs: list[DiscoveredJob]) -> list[DiscoveredJob]:
    seen: set[str] = set()
    unique: list[DiscoveredJob] = []

    for job in jobs:
        fingerprint = build_job_fingerprint(job)

        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        unique.append(job)

    return unique


def render_markdown_table(reports: list[ProviderReport]) -> str:
    """
    Render the AJI-018C comparison table: one column per provider, rows in
    ``REPORT_ROWS`` order, no ranking/score/winner column.
    """

    header = "| Metric | " + " | ".join(r.provider for r in reports) + " |"
    separator = "|---|" + "|".join("---" for _ in reports) + "|"

    rows = []
    row_values = [report.as_row_values() for report in reports]
    for metric in REPORT_ROWS:
        cells = " | ".join(values[metric] for values in row_values)
        rows.append(f"| {metric} | {cells} |")

    lines = [header, separator, *rows]

    error_lines = _render_error_notes(reports)
    if error_lines:
        lines.append("")
        lines.extend(error_lines)

    return "\n".join(lines)


def _render_error_notes(reports: list[ProviderReport]) -> list[str]:
    lines = []

    for report in reports:
        if not report.scenario_errors:
            continue

        lines.append(f"**{report.provider} scenario errors:**")
        for scenario_id, error in report.scenario_errors.items():
            lines.append(f"- `{scenario_id}`: {error}")

    return lines
