"""Hard Eligibility orchestration service.

This is the database-touching layer between the /jobs router and the
pure, DB-free services.eligibility engine (which decides eligibility but
never accesses the database or calls an LLM — see
services/eligibility/engine.py's own docstring for that boundary).

Building a job's eligibility signals reuses
services.job_matching.extractor.extract_experience_requirements for its
minimum-years-of-experience detection rather than introducing a second
regex-based parser, per docs/ARCHITECTURE.md's "reuse existing
architecture" guidance.

Performance: evaluate_jobs_eligibility() builds the user's
UserEligibilityCriteria exactly once and reuses it across every job, and
never issues a database query per job — callers are expected to have
already loaded the ``jobs`` list (e.g. from the existing paginated job
listing query in apps/api/routers/jobs.py).
"""

from __future__ import annotations

from uuid import UUID

from apps.api.models import Job, Preference, Profile, User
from services.eligibility.contracts import (
    EligibilityResult,
    JobEligibilitySignals,
    UserEligibilityCriteria,
)
from services.eligibility.engine import evaluate_eligibility
from services.eligibility.job_signals import extract_work_authorization_signals
from services.job_matching.extractor import extract_experience_requirements


def _build_user_criteria(
    *,
    preference: Preference | None,
    profile: Profile | None,
) -> UserEligibilityCriteria:
    return UserEligibilityCriteria(
        allowed_employment_types=(
            preference.employment_types if preference else None
        ),
        included_locations=(
            preference.locations if preference else None
        ),
        excluded_locations=(
            preference.excluded_locations if preference else None
        ),
        required_remote_type=(
            preference.remote_preference if preference else None
        ),
        requires_sponsorship=(
            preference.requires_sponsorship if preference else None
        ),
        is_us_citizen=(
            preference.is_us_citizen if preference else None
        ),
        has_security_clearance=(
            preference.has_security_clearance if preference else None
        ),
        enforce_minimum_experience=bool(
            preference.enforce_minimum_experience if preference else False
        ),
        user_years_experience=(
            profile.years_experience if profile else None
        ),
    )


def _build_job_signals(job: Job) -> JobEligibilitySignals:
    text = "\n".join(
        part
        for part in [job.requirements, job.responsibilities, job.description]
        if part
    )

    minimum_years_candidates = [
        requirement.minimum_years
        for requirement in extract_experience_requirements(text)
        if requirement.minimum_years is not None
    ]

    return JobEligibilitySignals(
        employment_type=job.employment_type,
        location=job.location,
        remote_type=job.remote_type,
        work_authorization=extract_work_authorization_signals(text),
        minimum_years_required=(
            max(minimum_years_candidates)
            if minimum_years_candidates
            else None
        ),
    )


def evaluate_job_eligibility(
    *,
    current_user: User,
    job: Job,
) -> EligibilityResult:
    """
    Evaluate a single job's hard eligibility for the authenticated user.
    """
    criteria = _build_user_criteria(
        preference=current_user.preferences,
        profile=current_user.profile,
    )

    return evaluate_eligibility(criteria, _build_job_signals(job))


def evaluate_jobs_eligibility(
    *,
    current_user: User,
    jobs: list[Job],
) -> dict[UUID, EligibilityResult]:
    """
    Evaluate hard eligibility for many jobs against one user in a single
    pass, keyed by job id. Intended for future bulk consumers (e.g. an
    "Eligible Jobs" pipeline step) that already have a loaded job list.
    """
    criteria = _build_user_criteria(
        preference=current_user.preferences,
        profile=current_user.profile,
    )

    return {
        job.id: evaluate_eligibility(criteria, _build_job_signals(job))
        for job in jobs
    }
