"""Resume Improvement Approval & Recheck orchestration service (AJI-021).

The database-touching layer between the /jobs router and the pure,
DB-free `engine` module - the same DB/pure-core split
`apps.api.services.gap_analysis.service` uses for Gap Analysis and
`apps.api.services.ats_alignment_service` uses for ATS Alignment.

Source data (reused, never recreated):

- **Which suggestions exist** comes entirely from an existing AJI-015
  `GapAnalysis` row, read by id. This service never calls a Gap Analysis
  provider, never re-selects gaps, and never re-runs
  `generate_gap_analysis()`.
- **The baseline score** is the `AtsAlignmentResult` that Gap Analysis
  row was already derived from (`GapAnalysis.ats_alignment_id`) - no
  "before" analysis is recomputed.
- **The recheck score** is produced by calling the existing, unmodified
  `calculate_ats_alignment()` with the *same* `job_id` and the newly
  created child `resume_version_id`. Nothing under
  `services/ats_alignment` is touched: the scoring formula, its
  weights, and `ENGINE_VERSION` are exactly what they were.

Two explicit steps, not one: `create_resume_improvement` creates the
child version and returns with `recheck_status = "pending"`. It does
*not* run the recheck. `run_recheck` is a separate call the user
triggers ("Run recheck" in Figma 09), and is also the retry path after a
failure - the same code, because both do the same thing.

Ordering guarantee (the ticket's "preserve the new version if recheck
fails" rule): the child `ResumeVersion` and the `ResumeImprovement` row
are committed before any recheck is attempted, and a recheck failure
only ever writes `recheck_status`/`recheck_error` onto the already-
durable row. There is no code path in which a failed, slow, crashed, or
never-run recheck removes, rolls back, or invalidates a version the user
approved - leaving the page without running it keeps the version.

Ownership: every lookup here is scoped to the requesting user's own
`user_id`, and the parent `ResumeVersion` is additionally re-verified
through `Resume.user_id` rather than trusted because it was referenced
by a Gap Analysis row. A not-owned or nonexistent resource returns the
same 404 as any other unowned resource in this API, so existence is
never leaked.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import (
    AtsAlignmentResult,
    GapAnalysis,
    Resume,
    ResumeImprovement,
    ResumeVersion,
    User,
)
from apps.api.services.ats_alignment_service import (
    ATSAlignmentServiceError,
    calculate_ats_alignment,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint
from apps.api.services.resume_improvement.contracts import (
    ResumeImprovementResult,
)
from apps.api.services.resume_improvement.engine import (
    ENGINE_VERSION,
    GapReference,
    ImprovementValidationError,
    ValidatedDecision,
    build_comparison,
    build_improved_content,
    compute_approval_fingerprint,
    next_improvement_version_name,
    validate_decisions,
)


logger = logging.getLogger(__name__)


class ResumeImprovementServiceError(RuntimeError):
    """Application-level error for Resume Improvement orchestration
    failures. `code` is a stable identifier the frontend can branch on
    without matching on prose."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: str = "error",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


# ---------------------------------------------------------------------------
# Read (never computes, never creates a version, never calls the ATS engine)
# ---------------------------------------------------------------------------

def get_latest_resume_improvement(
    db: Session,
    *,
    user_id: UUID,
    job_id: UUID,
    parent_resume_version_id: UUID | None = None,
) -> ResumeImprovement | None:
    """Read-only lookup of this user's newest Resume Improvement record
    for a job, optionally pinned to the parent version it was based on.
    """
    query = db.query(ResumeImprovement).filter(
        ResumeImprovement.user_id == user_id,
        ResumeImprovement.job_id == job_id,
    )

    if parent_resume_version_id is not None:
        query = query.filter(
            ResumeImprovement.parent_resume_version_id
            == parent_resume_version_id
        )

    return query.order_by(ResumeImprovement.created_at.desc()).first()


def get_resume_improvement(
    db: Session,
    *,
    user_id: UUID,
    improvement_id: UUID,
) -> ResumeImprovement | None:
    """Ownership-scoped lookup by id. Never filters on id alone."""
    return (
        db.query(ResumeImprovement)
        .filter(
            ResumeImprovement.id == improvement_id,
            ResumeImprovement.user_id == user_id,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_gap_analysis(
    db: Session,
    *,
    user_id: UUID,
    job_id: UUID,
    gap_analysis_id: UUID,
) -> GapAnalysis:
    record = (
        db.query(GapAnalysis)
        .filter(
            GapAnalysis.id == gap_analysis_id,
            GapAnalysis.user_id == user_id,
            GapAnalysis.job_id == job_id,
        )
        .first()
    )

    if record is None:
        raise ResumeImprovementServiceError(
            "Gap Analysis not found.",
            status_code=404,
            code="gap_analysis_not_found",
        )

    return record


def _load_owned_resume_version(
    db: Session,
    *,
    user_id: UUID,
    resume_version_id: UUID,
) -> ResumeVersion:
    """Re-verify ownership through `Resume.user_id` rather than trusting
    that the id came from a row already scoped to this user."""
    version = (
        db.query(ResumeVersion)
        .join(ResumeVersion.resume)
        .filter(
            ResumeVersion.id == resume_version_id,
            Resume.user_id == user_id,
        )
        .first()
    )

    if version is None:
        raise ResumeImprovementServiceError(
            "Resume version not found.",
            status_code=404,
            code="resume_version_not_found",
        )

    return version


def _gap_references(record: GapAnalysis) -> dict[str, GapReference]:
    """Build the engine's view of the stored gaps.

    `suggestion_type` is read from here - the persisted Gap Analysis row
    - and never from the request body, which is what makes the
    `ADD_IF_TRUE` truth-confirmation check impossible to bypass from the
    client.
    """
    references: dict[str, GapReference] = {}

    for gap in record.result.get("gaps", []):
        requirement_id = gap.get("requirement_id")

        if not requirement_id:
            continue

        references[requirement_id] = GapReference(
            requirement_id=requirement_id,
            requirement_text=gap.get("requirement_text", ""),
            category=gap.get("category", "preferred"),
            suggestion_type=gap.get("suggestion_type", "ADD_IF_TRUE"),
        )

    return references


def _decision_records(decisions: list[ValidatedDecision]) -> list[dict]:
    return [
        {
            "requirement_id": decision.requirement_id,
            "requirement_text": decision.requirement_text,
            "category": decision.category,
            "suggestion_type": decision.suggestion_type,
            "action": decision.action,
            "truth_confirmed": decision.truth_confirmed,
            "applied_text": decision.applied_text,
            "content_source": decision.content_source,
        }
        for decision in decisions
    ]


def _approved_requirement_ids(record: ResumeImprovement) -> set[str]:
    return {
        decision["requirement_id"]
        for decision in record.result.get("decisions", [])
        if decision.get("action") == "approve"
    }


def _attach_comparison(
    db: Session,
    record: ResumeImprovement,
    recheck: AtsAlignmentResult,
) -> None:
    """Write the before/after comparison onto an already-persisted
    improvement row. Pure arithmetic over two stored ATS results - see
    `engine.build_comparison`."""
    baseline = (
        db.query(AtsAlignmentResult)
        .filter(
            AtsAlignmentResult.id == record.baseline_ats_alignment_id,
            AtsAlignmentResult.user_id == record.user_id,
        )
        .first()
    )

    if baseline is None:
        # The baseline row is immutable and FK-protected, so this is
        # only reachable if the user's data was deleted mid-flight. The
        # version and the decisions are still valid; only the "before"
        # side of the comparison is unavailable.
        logger.error(
            "Baseline ATS Alignment %s missing for resume improvement %s",
            record.baseline_ats_alignment_id,
            record.id,
        )
        return

    result = dict(record.result)
    result["comparison"] = build_comparison(
        baseline_id=str(baseline.id),
        baseline_resume_version_id=str(baseline.resume_version_id),
        baseline_score=baseline.overall_score,
        baseline_result=baseline.result,
        recheck_id=str(recheck.id),
        recheck_resume_version_id=str(recheck.resume_version_id),
        recheck_score=recheck.overall_score,
        recheck_result=recheck.result,
        approved_requirement_ids=_approved_requirement_ids(record),
    )

    # Validate before persisting, so a malformed comparison surfaces
    # here rather than as an unreadable stored row.
    ResumeImprovementResult.model_validate(result)

    record.result = result


def _run_recheck(
    *,
    db: Session,
    current_user: User,
    record: ResumeImprovement,
) -> ResumeImprovement:
    """Recheck the child version against the same job and record the
    outcome.

    Called only after `record` and its child version are already
    committed. Every failure path here leaves both of them intact and
    only updates the recheck fields - that is the whole point of running
    this as a separate step.

    The attempt runs inside a SAVEPOINT rather than relying on
    `Session.rollback()` for cleanup. `Session.rollback()` unwinds the
    *outermost* session transaction, which in any caller that has joined
    this session to an enclosing transaction would discard the
    just-committed child version along with the failed attempt's
    leftovers - the exact outcome the "preserve the new version if the
    recheck fails" rule forbids. A SAVEPOINT undoes only what this
    attempt itself wrote.
    """
    record_id = record.id
    savepoint = db.begin_nested()

    try:
        recheck = calculate_ats_alignment(
            db=db,
            current_user=current_user,
            job_id=record.job_id,
            resume_version_id=record.child_resume_version_id,
        )
    except Exception as exc:
        # Deliberately broad: no failure of the recheck may be allowed to
        # propagate in a way that loses the approved version.
        logger.error(
            "Resume Improvement recheck failed for improvement %s "
            "(job %s, child version %s): %s",
            record_id,
            record.job_id,
            record.child_resume_version_id,
            exc,
        )

        if savepoint.is_active:
            savepoint.rollback()

        refreshed = db.get(ResumeImprovement, record_id)

        if refreshed is None:
            raise

        refreshed.recheck_status = "failed"
        # `ATSAlignmentServiceError` messages are the user-facing strings
        # the ATS endpoints already return ("Job not found", "Resume
        # version contains no readable text."). Anything else is an
        # unexpected internal failure, whose text is logged above but
        # never surfaced.
        refreshed.recheck_error = (
            str(exc)
            if isinstance(exc, ATSAlignmentServiceError)
            else "The recheck could not be completed."
        )
        db.commit()
        db.refresh(refreshed)

        return refreshed

    # `calculate_ats_alignment` commits on success, which releases the
    # savepoint above; re-read the record rather than assuming this
    # session still holds a live instance of it.
    record = db.get(ResumeImprovement, record_id)

    record.recheck_ats_alignment_id = recheck.id
    record.recheck_status = "complete"
    record.recheck_error = None

    _attach_comparison(db, record, recheck)

    db.commit()
    db.refresh(record)

    return record


# ---------------------------------------------------------------------------
# Create-or-reuse
# ---------------------------------------------------------------------------

def create_resume_improvement(
    *,
    db: Session,
    current_user: User,
    job_id: UUID,
    gap_analysis_id: UUID,
    decisions: list[dict],
) -> ResumeImprovement:
    """Apply the user's approved suggestions: create a child
    `ResumeVersion`, then recheck it against the same job.

    Idempotent by approval content: re-submitting the same approvals for
    the same Gap Analysis returns the existing record rather than
    creating a second child version. The database's own unique
    constraint on `(user_id, gap_analysis_id, approval_fingerprint)`
    backs this up, so two concurrent requests cannot both create one.
    """
    gap_analysis = _load_gap_analysis(
        db,
        user_id=current_user.id,
        job_id=job_id,
        gap_analysis_id=gap_analysis_id,
    )

    parent_version = _load_owned_resume_version(
        db,
        user_id=current_user.id,
        resume_version_id=gap_analysis.resume_version_id,
    )

    try:
        validated = validate_decisions(
            decisions=decisions,
            gaps_by_requirement_id=_gap_references(gap_analysis),
        )
    except ImprovementValidationError as exc:
        raise ResumeImprovementServiceError(
            exc.message,
            status_code=422,
            code=exc.code,
        ) from exc

    fingerprint = compute_approval_fingerprint(
        gap_analysis_id=str(gap_analysis.id),
        parent_resume_version_id=str(parent_version.id),
        decisions=validated,
    )

    existing = _find_by_fingerprint(
        db,
        user_id=current_user.id,
        gap_analysis_id=gap_analysis.id,
        fingerprint=fingerprint,
    )

    if existing is not None:
        # The same approvals were already applied: the child version
        # they produced is returned as-is rather than being created a
        # second time.
        return existing

    improved_content = build_improved_content(
        parent_content=parent_version.content_text,
        decisions=validated,
    )

    if improved_content.strip() == parent_version.content_text.strip():
        raise ResumeImprovementServiceError(
            "The approved changes would not alter your resume.",
            status_code=422,
            code="no_change",
        )

    child_version = _create_child_version(
        db,
        parent_version=parent_version,
        content=improved_content,
    )

    record = ResumeImprovement(
        user_id=current_user.id,
        job_id=job_id,
        gap_analysis_id=gap_analysis.id,
        baseline_ats_alignment_id=gap_analysis.ats_alignment_id,
        parent_resume_version_id=parent_version.id,
        child_resume_version_id=child_version.id,
        approval_fingerprint=fingerprint,
        engine_version=ENGINE_VERSION,
        approved_count=sum(
            1 for decision in validated if decision.action == "approve"
        ),
        skipped_count=sum(
            1 for decision in validated if decision.action == "skip"
        ),
        # Committed before the recheck runs, so the version survives
        # even if the process dies between the two.
        recheck_status="pending",
        result=ResumeImprovementResult(
            engine_version=ENGINE_VERSION,
            job_id=str(job_id),
            gap_analysis_id=str(gap_analysis.id),
            parent_resume_version_id=str(parent_version.id),
            child_resume_version_id=str(child_version.id),
            child_resume_version_name=child_version.name,
            parent_resume_version_name=parent_version.name,
            approved_count=sum(
                1 for decision in validated if decision.action == "approve"
            ),
            skipped_count=sum(
                1 for decision in validated if decision.action == "skip"
            ),
            decisions=_decision_records(validated),
        ).model_dump(mode="json"),
    )

    db.add(record)

    try:
        db.commit()
    except IntegrityError:
        # A concurrent request won the race on the unique constraint.
        # Both the child version and this record roll back together, so
        # no orphan version is left behind, and the winner's record is
        # returned instead of a duplicate.
        db.rollback()

        existing = _find_by_fingerprint(
            db,
            user_id=current_user.id,
            gap_analysis_id=gap_analysis.id,
            fingerprint=fingerprint,
        )

        if existing is not None:
            return existing

        raise ResumeImprovementServiceError(
            "Unable to save these approved improvements.",
            status_code=500,
            code="persist_failed",
        )

    db.refresh(record)

    # The recheck is NOT run here. Creating the version and rechecking it
    # are two explicit user steps (Figma 09: "Run recheck"), so this
    # returns with `recheck_status = "pending"` and the caller decides
    # when to run it. The version is already committed at this point, so
    # leaving without ever running the recheck still leaves it persisted
    # and recoverable.
    return record


def run_recheck(
    *,
    db: Session,
    current_user: User,
    job_id: UUID,
    improvement_id: UUID,
) -> ResumeImprovement:
    """Run the recheck for an existing improvement record.

    This is both the initial "Run recheck" action and the retry after a
    failure - one code path, because they do exactly the same thing: the
    version and the decisions are already durable either way.

    Never creates a version and never re-applies decisions. A record
    whose recheck already succeeded is returned unchanged - a completed
    recheck's `recheck_ats_alignment_id` is never re-pointed, so the
    comparison the user was shown cannot silently change underneath
    them.
    """
    record = get_resume_improvement(
        db,
        user_id=current_user.id,
        improvement_id=improvement_id,
    )

    if record is None or record.job_id != job_id:
        raise ResumeImprovementServiceError(
            "Resume improvement not found.",
            status_code=404,
            code="improvement_not_found",
        )

    if (
        record.recheck_status == "complete"
        and record.recheck_ats_alignment_id is not None
    ):
        return record

    return _run_recheck(db=db, current_user=current_user, record=record)


# ---------------------------------------------------------------------------
# Small internal helpers kept below the public surface
# ---------------------------------------------------------------------------

def _find_by_fingerprint(
    db: Session,
    *,
    user_id: UUID,
    gap_analysis_id: UUID,
    fingerprint: str,
) -> ResumeImprovement | None:
    return (
        db.query(ResumeImprovement)
        .filter(
            ResumeImprovement.user_id == user_id,
            ResumeImprovement.gap_analysis_id == gap_analysis_id,
            ResumeImprovement.approval_fingerprint == fingerprint,
        )
        .first()
    )


def _create_child_version(
    db: Session,
    *,
    parent_version: ResumeVersion,
    content: str,
) -> ResumeVersion:
    """Create the child version.

    The parent row is read and never written: its text, its file, its
    name, and its `is_master` flag are all left exactly as they were.
    The child is always `is_master=False` - approving suggestions for
    one job never silently repoints the user's master resume.
    """
    existing_names = [
        row[0]
        for row in db.query(ResumeVersion.name)
        .filter(ResumeVersion.resume_id == parent_version.resume_id)
        .all()
    ]

    child = ResumeVersion(
        resume_id=parent_version.resume_id,
        name=next_improvement_version_name(existing_names),
        content_text=content,
        content_fingerprint=compute_content_fingerprint(content),
        # The document this version's text descends from. There is no
        # new uploaded file, so `storage_path` stays NULL and
        # `GET /resumes/versions/{id}/file` 404s for it rather than
        # serving the parent's file under a child's name.
        original_filename=parent_version.original_filename,
        storage_path=None,
        parent_version_id=parent_version.id,
        source="improvement",
        is_master=False,
    )

    db.add(child)
    db.flush()

    return child
