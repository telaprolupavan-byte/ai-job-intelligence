"""Job Priority Ranking orchestration service (AJI-025).

The database-touching layer between GET /jobs/priority and the pure,
DB-free, AI-free services.priority_ranking engine - the same DB/pure-core
split eligibility_service.py uses for services.eligibility.

What it reads (and why nothing else):

- **Hard Eligibility** - evaluated fresh on every request through the
  existing `evaluate_jobs_eligibility()` (criteria built once, pure, no
  writes), so a preference change is reflected immediately and a stale
  `JobEligibilityResult` row can never be used.
- **Job Match** and **ATS Alignment** - the user's own latest persisted
  result for each job, pinned to ONE resume version: the explicit
  `resume_version_id`, or the same default Job Match already uses
  (`job_match_service._resolve_resume_version`, reused rather than copied,
  so there is no second resume-version-selection rule). Match and ATS for
  a different resume version are never read, so results are never mixed.
- The latest **Job Intelligence** / **Requirement Intelligence** snapshot
  ids - only to tell whether a stored Match/ATS is still current (see
  services/priority_ranking/engine.py). Their content is not read.

Nothing else participates: Gap Analysis is derived from ATS Alignment
(using it would count the same evidence twice), Resume Improvement acts
through the resume version the user selects, and Application Tracking
status has no approved effect on priority.

What it never does: write anything, call an AI provider, or compute a
missing analysis. A job the user has not analyzed for this resume version
is not ranked - it is counted as unanalyzed. Priority is recomputed on
every request (it is cheap), so there is no stored ranking to go stale.

Scope and privacy: candidate jobs are exactly the rows the Jobs listing
query (`job_listing_query`) returns for this user - active, visible
(discovered, or the caller's own submissions; test-fixture jobs only in
test mode), and narrowed by the same optional filters - AND for which this
user has a Job Match or ATS Alignment for the pinned resume version. Every
analysis query filters on the caller's own `user_id`.

Performance: a fixed number of queries regardless of how many jobs are
ranked - one per artifact type, using Postgres `DISTINCT ON` to take the
latest row per job - never one query per job.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.models import (
    AtsAlignmentResult,
    Job,
    JobIntelligence,
    JobMatchResult,
    RequirementIntelligence,
    ResumeVersion,
    User,
)
from apps.api.services.eligibility_service import evaluate_jobs_eligibility
from apps.api.services.job_listing import job_listing_query
from apps.api.services.job_match_service import (
    JobMatchServiceError,
    _resolve_resume_version,
)
from services.eligibility.contracts import EligibilityResult
from services.priority_ranking.contracts import (
    AtsAlignmentEvidence,
    JobMatchEvidence,
    PriorityCandidate,
    PriorityResult,
    PriorityState,
)
from services.priority_ranking.engine import rank_jobs


class PriorityRankingServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PriorityItem:
    result: PriorityResult
    job: Job
    company_name: str | None
    eligibility: EligibilityResult
    job_match: JobMatchResult | None
    ats_alignment: AtsAlignmentResult | None


@dataclass
class JobPriorityOutcome:
    resume_version: ResumeVersion | None
    # The requested page, in priority order.
    items: list[PriorityItem]
    # Totals over the whole (filtered) candidate set, not just this page.
    total: int
    state_counts: dict[str, int]
    # Visible jobs matching the filters with no Job Match and no ATS
    # Alignment for this resume version - not ranked, not listed.
    unanalyzed_count: int


def _resolve_pinned_resume_version(
    db: Session,
    *,
    current_user: User,
    resume_version_id: UUID | None,
) -> ResumeVersion | None:
    try:
        return _resolve_resume_version(
            db,
            current_user=current_user,
            resume_version_id=resume_version_id,
        )
    except JobMatchServiceError as exc:
        # An explicit version the user doesn't own is the same 404 as on
        # every other per-resume endpoint. Having no resume at all is not
        # an error here: there is simply nothing to rank yet.
        if resume_version_id is not None or exc.status_code != 404:
            raise PriorityRankingServiceError(
                str(exc), status_code=exc.status_code
            ) from exc

        return None


def _latest_per_job(db: Session, model, *filters):
    """The newest row of `model` per job_id - the same "latest" rule
    (created_at DESC) the single-job get_latest_* lookups use."""
    return (
        db.execute(
            select(model)
            .where(*filters)
            .order_by(model.job_id, model.created_at.desc(), model.id.desc())
            .distinct(model.job_id)
        )
        .scalars()
        .all()
    )


def _latest_snapshot_ids(db: Session, model, *filters) -> dict[UUID, UUID]:
    rows = db.execute(
        select(model.job_id, model.id)
        .where(*filters)
        .order_by(model.job_id, model.created_at.desc(), model.id.desc())
        .distinct(model.job_id)
    ).all()

    return {job_id: snapshot_id for job_id, snapshot_id in rows}


def _match_evidence(record: JobMatchResult) -> JobMatchEvidence:
    result = record.result or {}
    matched = len(result.get("must_have_matches") or [])
    gaps = len(result.get("must_have_gaps") or [])

    return JobMatchEvidence(
        id=str(record.id),
        score=record.score,
        engine_version=record.engine_version,
        job_intelligence_id=(
            str(record.job_intelligence_id)
            if record.job_intelligence_id
            else None
        ),
        must_have_matched=matched,
        must_have_total=matched + gaps,
    )


def _ats_evidence(record: AtsAlignmentResult) -> AtsAlignmentEvidence:
    result = record.result or {}

    return AtsAlignmentEvidence(
        id=str(record.id),
        overall_score=record.overall_score,
        engine_version=record.engine_version,
        job_intelligence_id=str(record.job_intelligence_id),
        requirement_intelligence_id=(
            str(record.requirement_intelligence_id)
            if record.requirement_intelligence_id
            else None
        ),
        must_have_matched=int(result.get("must_have_matched") or 0),
        must_have_total=int(result.get("must_have_total") or 0),
    )


def build_job_priority(
    db: Session,
    *,
    current_user: User,
    resume_version_id: UUID | None = None,
    search: str | None = None,
    employment_type: str | None = None,
    remote_type: str | None = None,
    location: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> JobPriorityOutcome:
    """Order the user's analyzed jobs for attention (read-only)."""
    resume_version = _resolve_pinned_resume_version(
        db,
        current_user=current_user,
        resume_version_id=resume_version_id,
    )

    scope = job_listing_query(
        user_id=current_user.id,
        search=search,
        employment_type=employment_type,
        remote_type=remote_type,
        location=location,
    )
    scope_job_ids = scope.with_only_columns(Job.id)

    scope_total = db.scalar(
        select(func.count()).select_from(scope_job_ids.subquery())
    ) or 0

    if resume_version is None:
        return JobPriorityOutcome(
            resume_version=None,
            items=[],
            total=0,
            state_counts={state.value: 0 for state in PriorityState},
            unanalyzed_count=scope_total,
        )

    matches = {
        record.job_id: record
        for record in _latest_per_job(
            db,
            JobMatchResult,
            JobMatchResult.user_id == current_user.id,
            JobMatchResult.resume_version_id == resume_version.id,
            JobMatchResult.job_id.in_(scope_job_ids),
        )
    }

    ats_results = {
        record.job_id: record
        for record in _latest_per_job(
            db,
            AtsAlignmentResult,
            AtsAlignmentResult.user_id == current_user.id,
            AtsAlignmentResult.resume_version_id == resume_version.id,
            AtsAlignmentResult.job_id.in_(scope_job_ids),
        )
    }

    candidate_ids = set(matches) | set(ats_results)

    jobs: dict[UUID, tuple[Job, str | None]] = {}
    latest_ji: dict[UUID, UUID] = {}
    latest_ri: dict[UUID, UUID] = {}

    if candidate_ids:
        jobs = {
            job.id: (job, company_name)
            for job, company_name in db.execute(
                scope.where(Job.id.in_(candidate_ids))
            ).all()
        }

        latest_ji = _latest_snapshot_ids(
            db,
            JobIntelligence,
            JobIntelligence.job_id.in_(candidate_ids),
        )

        latest_ri = _latest_snapshot_ids(
            db,
            RequirementIntelligence,
            RequirementIntelligence.user_id == current_user.id,
            RequirementIntelligence.job_id.in_(candidate_ids),
        )

    eligibility = (
        evaluate_jobs_eligibility(
            current_user=current_user,
            jobs=[job for job, _ in jobs.values()],
        )
        if jobs
        else {}
    )

    candidates = [
        PriorityCandidate(
            job_id=str(job_id),
            posting_date=job.posting_date,
            eligibility=eligibility[job_id],
            job_match=(
                _match_evidence(matches[job_id]) if job_id in matches else None
            ),
            ats_alignment=(
                _ats_evidence(ats_results[job_id])
                if job_id in ats_results
                else None
            ),
            latest_job_intelligence_id=(
                str(latest_ji[job_id]) if job_id in latest_ji else None
            ),
            latest_requirement_intelligence_id=(
                str(latest_ri[job_id]) if job_id in latest_ri else None
            ),
        )
        for job_id, (job, _) in jobs.items()
    ]

    ranked = rank_jobs(candidates)

    state_counts = {state.value: 0 for state in PriorityState}
    for result in ranked:
        state_counts[result.state.value] += 1

    offset = (page - 1) * page_size
    items: list[PriorityItem] = []

    for result in ranked[offset:offset + page_size]:
        job_id = UUID(result.job_id)
        job, company_name = jobs[job_id]
        items.append(
            PriorityItem(
                result=result,
                job=job,
                company_name=company_name,
                eligibility=eligibility[job_id],
                job_match=matches.get(job_id),
                ats_alignment=ats_results.get(job_id),
            )
        )

    return JobPriorityOutcome(
        resume_version=resume_version,
        items=items,
        total=len(ranked),
        state_counts=state_counts,
        unanalyzed_count=scope_total - len(jobs),
    )
