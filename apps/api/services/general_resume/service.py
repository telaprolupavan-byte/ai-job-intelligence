"""General Resume Intelligence orchestration (AJI-027).

The DB-touching layer between `apps/api/routers/general_resume.py` and the
pure modules in this package (`scoring`, `improvements`, `engine`,
`validator`) - the same DB/pure-core split the other analysis pipelines
use.

Job independence: nothing here reads a `Job`, a requirement snapshot, an
ATS/Job Match/Gap Analysis row, or a preference. The only input to an
assessment is one resume version's text.

Ordering guarantees (mirroring AJI-021):

- A review's child version and its review row are committed *before* the
  recheck runs. The recheck runs inside a SAVEPOINT, and a failure only
  writes `recheck_status`/`recheck_error` onto the durable review; the
  version is never removed. `run_review_recheck` retries it.
- Inserts that can race (an assessment, a review + its child version) run
  inside their own SAVEPOINT, so losing a unique-constraint race rolls
  back only that insert and returns the winner's row - never the
  caller's enclosing transaction.

Ownership: every lookup is scoped to the requesting user. A not-owned or
nonexistent resource is the same 404, so existence is never leaked.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import (
    GeneralResumeAssessment,
    GeneralResumeReview,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services.general_resume.contracts import (
    AssessmentComparison,
    ComponentDelta,
    GeneralResumeAssessmentResult,
    Improvement,
    ImprovementChange,
    ReviewDecisionRecord,
    ValidationSummary,
)
from apps.api.services.general_resume.engine import (
    ENGINE_VERSION,
    VERSION_SOURCE,
    ReviewValidationError,
    ValidatedDecision,
    build_refined_content,
    compute_review_fingerprint,
    next_refined_version_name,
    validate_review_decisions,
)
from apps.api.services.general_resume.improvements import (
    ANALYZER_VERSION,
    detect_improvements,
)
from apps.api.services.general_resume.interpreter import (
    PROMPT_VERSION,
    GeneralResumeInterpreter,
)
from apps.api.services.general_resume.providers import (
    create_general_resume_provider,
)
from apps.api.services.general_resume.scoring import (
    SCORING_VERSION,
    score_resume,
)
from apps.api.services.general_resume.validator import (
    ai_request_items,
    merge_ai_explanations,
)
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint
from apps.api.services.resume_validation import validate_resume_text


ANALYSIS_VERSION = "1.0"

# Bound on the parent-version walk used for rejection carry-forward.
MAX_LINEAGE_DEPTH = 100

logger = logging.getLogger(__name__)


class GeneralResumeServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: str = "error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


# ---------------------------------------------------------------------------
# Deterministic assessment (no DB, no AI)
# ---------------------------------------------------------------------------

def compute_deterministic_assessment(text: str):
    """Score, improvements and validation for one resume text. Pure and
    deterministic; the AI stage runs after this and cannot change it."""
    analysis = analyze_resume_deterministically(text)
    score = score_resume(analysis)
    insufficient = {
        component.key
        for component in score.components
        if component.status == "insufficient_data"
    }
    improvements = detect_improvements(text, analysis, insufficient)
    validation = validate_resume_text(text)

    return (
        score,
        improvements,
        ValidationSummary(
            valid=validation.valid,
            warnings=validation.warnings,
            word_count=validation.word_count,
            section_matches=validation.section_matches,
        ),
    )


def _enrich_with_ai(
    improvements: list[Improvement],
) -> tuple[list[Improvement], str, str | None, str | None]:
    """Optional AI explanations. Returns (improvements, generation_status,
    model_provider, model_name). Any failure keeps every template and
    reports "partial"; it can never affect the score or the list."""
    items = ai_request_items(improvements)

    if not items:
        return improvements, "complete", None, None

    try:
        provider = create_general_resume_provider()
        interpretation = GeneralResumeInterpreter(provider).explain(items=items)
    except Exception as exc:
        # Deliberately broad: no AI failure (provider error, timeout, no
        # key, malformed output) may block or alter an assessment.
        logger.warning("General Resume AI enrichment unavailable: %s", exc)
        return improvements, "partial", None, None

    return (
        merge_ai_explanations(improvements, interpretation.result),
        "complete",
        interpretation.provider,
        interpretation.model,
    )


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def _load_owned_version(
    db: Session,
    *,
    user_id: UUID,
    resume_version_id: UUID,
) -> ResumeVersion:
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
        raise GeneralResumeServiceError(
            "Resume version not found.",
            status_code=404,
            code="resume_version_not_found",
        )

    return version


def _current_assessment_query(db: Session, *, user_id: UUID, resume_version_id: UUID):
    return db.query(GeneralResumeAssessment).filter(
        GeneralResumeAssessment.user_id == user_id,
        GeneralResumeAssessment.resume_version_id == resume_version_id,
        GeneralResumeAssessment.analyzer_version == ANALYZER_VERSION,
        GeneralResumeAssessment.scoring_version == SCORING_VERSION,
        GeneralResumeAssessment.prompt_version == PROMPT_VERSION,
    )


def get_current_assessment(
    db: Session,
    *,
    user_id: UUID,
    resume_version_id: UUID,
) -> GeneralResumeAssessment | None:
    """The assessment produced by the current pipeline, or None. Never
    computes and never calls the AI."""
    _load_owned_version(db, user_id=user_id, resume_version_id=resume_version_id)

    return (
        _current_assessment_query(
            db, user_id=user_id, resume_version_id=resume_version_id
        )
        .order_by(GeneralResumeAssessment.created_at.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Assess (create-or-reuse)
# ---------------------------------------------------------------------------

def assess_resume_version(
    db: Session,
    *,
    user_id: UUID,
    resume_version_id: UUID,
) -> GeneralResumeAssessment:
    version = _load_owned_version(
        db, user_id=user_id, resume_version_id=resume_version_id
    )

    existing = (
        _current_assessment_query(
            db, user_id=user_id, resume_version_id=resume_version_id
        ).first()
    )

    if existing is not None:
        return existing

    text = (version.content_text or "").strip()

    if not text:
        raise GeneralResumeServiceError(
            "Resume version contains no readable text.",
            status_code=422,
            code="empty_resume",
        )

    score, improvements, validation = compute_deterministic_assessment(
        version.content_text
    )
    improvements, generation_status, provider, model = _enrich_with_ai(
        improvements
    )

    result = GeneralResumeAssessmentResult(
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        scoring_version=SCORING_VERSION,
        prompt_version=PROMPT_VERSION,
        resume_version_id=str(version.id),
        overall_score=score.overall_score,
        components=score.components,
        improvements=improvements,
        validation=validation,
        generation_status=generation_status,
    )

    row = GeneralResumeAssessment(
        user_id=user_id,
        resume_version_id=version.id,
        content_fingerprint=compute_content_fingerprint(version.content_text),
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        scoring_version=SCORING_VERSION,
        prompt_version=PROMPT_VERSION,
        model_provider=provider,
        model_name=model,
        overall_score=score.overall_score,
        generation_status=generation_status,
        result=result.model_dump(mode="json"),
    )

    savepoint = db.begin_nested()
    db.add(row)

    try:
        db.flush()
    except IntegrityError:
        # A concurrent request assessed the same version first.
        savepoint.rollback()
        winner = _current_assessment_query(
            db, user_id=user_id, resume_version_id=resume_version_id
        ).first()

        if winner is not None:
            return winner

        raise

    db.commit()
    db.refresh(row)

    return row


# ---------------------------------------------------------------------------
# Readiness (computed on read, never stored)
# ---------------------------------------------------------------------------

def _lineage_ids(db: Session, version: ResumeVersion) -> list[UUID]:
    ids = [version.id]
    parent_id = version.parent_version_id

    while parent_id is not None and len(ids) < MAX_LINEAGE_DEPTH:
        if parent_id in ids:
            break

        ids.append(parent_id)
        parent = db.get(ResumeVersion, parent_id)
        parent_id = parent.parent_version_id if parent is not None else None

    return ids


def rejected_improvement_ids(
    db: Session,
    *,
    user_id: UUID,
    version: ResumeVersion,
) -> set[str]:
    """Every improvement id this user rejected on this version or any of
    its ancestors. Ids are derived from the unchanged text an issue is
    anchored to, so a rejection carries forward exactly while the same
    underlying issue remains."""
    reviews = (
        db.query(GeneralResumeReview)
        .filter(
            GeneralResumeReview.user_id == user_id,
            GeneralResumeReview.parent_resume_version_id.in_(
                _lineage_ids(db, version)
            ),
        )
        .all()
    )

    return {
        decision["improvement_id"]
        for review in reviews
        for decision in review.decisions
        if decision.get("action") == "reject"
    }


def _latest_review(db: Session, *, user_id: UUID, assessment_id: UUID):
    return (
        db.query(GeneralResumeReview)
        .filter(
            GeneralResumeReview.user_id == user_id,
            GeneralResumeReview.assessment_id == assessment_id,
        )
        .order_by(GeneralResumeReview.created_at.desc())
        .first()
    )


def compute_readiness(
    db: Session,
    *,
    user_id: UUID,
    version: ResumeVersion,
    assessment: GeneralResumeAssessment | None,
) -> dict[str, Any]:
    """Ready = a current, valid assessment and no unresolved improvements
    (Product Owner definition). An improvement is resolved when it no
    longer appears (the text changed) or when the user rejected it on
    this version or an ancestor. No score threshold is involved - the
    score is not even read here."""
    readiness: dict[str, Any] = {
        "state": "not_assessed",
        "open_count": 0,
        "dismissed_count": 0,
        "refined_version_id": None,
    }

    if assessment is None:
        return readiness

    result = GeneralResumeAssessmentResult.model_validate(assessment.result)

    dismissed = rejected_improvement_ids(db, user_id=user_id, version=version)
    open_ids = [
        item.improvement_id
        for item in result.improvements
        if item.improvement_id not in dismissed
    ]

    readiness["open_count"] = len(open_ids)
    readiness["dismissed_count"] = len(result.improvements) - len(open_ids)

    if not result.validation.valid:
        readiness["state"] = "not_valid"
        return readiness

    latest = _latest_review(db, user_id=user_id, assessment_id=assessment.id)

    if latest is not None and latest.child_resume_version_id is not None:
        readiness["refined_version_id"] = str(latest.child_resume_version_id)
        readiness["state"] = {
            "pending": "recheck_pending",
            "failed": "recheck_failed",
        }.get(latest.recheck_status, "superseded")
        return readiness

    readiness["state"] = "ready" if not open_ids else "needs_review"

    return readiness


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_assessment(
    db: Session,
    *,
    user_id: UUID,
    assessment: GeneralResumeAssessment,
    include_review: bool = True,
) -> dict[str, Any]:
    version = _load_owned_version(
        db, user_id=user_id, resume_version_id=assessment.resume_version_id
    )
    result = GeneralResumeAssessmentResult.model_validate(assessment.result)
    dismissed = rejected_improvement_ids(db, user_id=user_id, version=version)

    payload = {
        "id": str(assessment.id),
        "resume_version_id": str(assessment.resume_version_id),
        "resume_version_name": version.name,
        "analysis_version": assessment.analysis_version,
        "analyzer_version": assessment.analyzer_version,
        "scoring_version": assessment.scoring_version,
        "prompt_version": assessment.prompt_version,
        "model_provider": assessment.model_provider,
        "model_name": assessment.model_name,
        "generation_status": assessment.generation_status,
        "overall_score": assessment.overall_score,
        "components": [c.model_dump(mode="json") for c in result.components],
        "improvements": [
            {
                **item.model_dump(mode="json", exclude={"anchor_line"}),
                "status": (
                    "dismissed" if item.improvement_id in dismissed else "open"
                ),
            }
            for item in result.improvements
        ],
        "validation": result.validation.model_dump(mode="json"),
        "readiness": compute_readiness(
            db, user_id=user_id, version=version, assessment=assessment
        ),
        "created_at": assessment.created_at.isoformat(),
        "latest_review": None,
    }

    if include_review:
        latest = _latest_review(db, user_id=user_id, assessment_id=assessment.id)

        if latest is not None:
            payload["latest_review"] = serialize_review(
                db, user_id=user_id, review=latest
            )

    return payload


def build_comparison(
    baseline: GeneralResumeAssessment,
    recheck: GeneralResumeAssessment,
    decisions: list[dict],
) -> AssessmentComparison:
    """Arithmetic over two stored assessment rows; nothing is re-scored."""
    before = GeneralResumeAssessmentResult.model_validate(baseline.result)
    after = GeneralResumeAssessmentResult.model_validate(recheck.result)

    after_components = {c.key: c for c in after.components}
    component_deltas = []

    for component in before.components:
        other = after_components.get(component.key)
        after_score = other.score if other else None
        delta = (
            round(after_score - component.score, 1)
            if after_score is not None and component.score is not None
            else None
        )
        component_deltas.append(
            ComponentDelta(
                key=component.key,
                label=component.label,
                before=component.score,
                after=after_score,
                delta=delta,
            )
        )

    approved = {d["improvement_id"] for d in decisions if d["action"] == "approve"}
    rejected = {d["improvement_id"] for d in decisions if d["action"] == "reject"}
    after_ids = {item.improvement_id for item in after.improvements}
    before_ids = {item.improvement_id for item in before.improvements}

    changes = [
        ImprovementChange(
            improvement_id=item.improvement_id,
            title=item.title,
            transition=(
                "still_present" if item.improvement_id in after_ids else "resolved"
            ),
            was_approved=item.improvement_id in approved,
            was_rejected=item.improvement_id in rejected,
        )
        for item in before.improvements
    ] + [
        ImprovementChange(
            improvement_id=item.improvement_id,
            title=item.title,
            transition="new",
        )
        for item in after.improvements
        if item.improvement_id not in before_ids
    ]

    return AssessmentComparison(
        baseline_assessment_id=str(baseline.id),
        baseline_resume_version_id=str(baseline.resume_version_id),
        baseline_score=baseline.overall_score,
        recheck_assessment_id=str(recheck.id),
        recheck_resume_version_id=str(recheck.resume_version_id),
        recheck_score=recheck.overall_score,
        score_delta=round(recheck.overall_score - baseline.overall_score, 1),
        components=component_deltas,
        resolved_count=sum(1 for c in changes if c.transition == "resolved"),
        still_present_count=sum(
            1 for c in changes if c.transition == "still_present"
        ),
        new_count=sum(1 for c in changes if c.transition == "new"),
        changes=changes,
    )


def serialize_review(
    db: Session,
    *,
    user_id: UUID,
    review: GeneralResumeReview,
) -> dict[str, Any]:
    parent = db.get(ResumeVersion, review.parent_resume_version_id)
    child = (
        db.get(ResumeVersion, review.child_resume_version_id)
        if review.child_resume_version_id
        else None
    )

    comparison = None
    readiness = None

    if review.recheck_assessment_id is not None:
        baseline = db.get(GeneralResumeAssessment, review.assessment_id)
        recheck = db.get(GeneralResumeAssessment, review.recheck_assessment_id)

        if baseline is not None and recheck is not None:
            comparison = build_comparison(
                baseline, recheck, review.decisions
            ).model_dump(mode="json")

            if child is not None:
                readiness = compute_readiness(
                    db, user_id=user_id, version=child, assessment=recheck
                )
    elif child is None and parent is not None:
        # Nothing was approved: the parent version stays the resume, and
        # its readiness now reflects the recorded rejections.
        readiness = compute_readiness(
            db,
            user_id=user_id,
            version=parent,
            assessment=db.get(GeneralResumeAssessment, review.assessment_id),
        )

    return {
        "id": str(review.id),
        "assessment_id": str(review.assessment_id),
        "parent_resume_version_id": str(review.parent_resume_version_id),
        "parent_resume_version_name": parent.name if parent else None,
        "child_resume_version_id": (
            str(review.child_resume_version_id)
            if review.child_resume_version_id
            else None
        ),
        "child_resume_version_name": child.name if child else None,
        "engine_version": review.engine_version,
        "approved_count": review.approved_count,
        "rejected_count": review.rejected_count,
        "decisions": review.decisions,
        "recheck_status": review.recheck_status,
        "recheck_error": review.recheck_error,
        "recheck_assessment_id": (
            str(review.recheck_assessment_id)
            if review.recheck_assessment_id
            else None
        ),
        "comparison": comparison,
        "resulting_readiness": readiness,
        "created_at": review.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Review: approve/reject, create version, recheck
# ---------------------------------------------------------------------------

def _decision_records(validated: list[ValidatedDecision]) -> list[dict]:
    return [
        ReviewDecisionRecord(
            improvement_id=d.improvement.improvement_id,
            kind=d.improvement.kind,
            suggestion_type=d.improvement.suggestion_type,
            title=d.improvement.title,
            action=d.action,
            truth_confirmed=d.truth_confirmed,
            applied_text=d.applied_text,
        ).model_dump(mode="json")
        for d in validated
    ]


def _find_review(db: Session, *, user_id: UUID, assessment_id: UUID, fingerprint: str):
    return (
        db.query(GeneralResumeReview)
        .filter(
            GeneralResumeReview.user_id == user_id,
            GeneralResumeReview.assessment_id == assessment_id,
            GeneralResumeReview.approval_fingerprint == fingerprint,
        )
        .first()
    )


def get_review(db: Session, *, user_id: UUID, review_id: UUID) -> GeneralResumeReview:
    review = (
        db.query(GeneralResumeReview)
        .filter(
            GeneralResumeReview.id == review_id,
            GeneralResumeReview.user_id == user_id,
        )
        .first()
    )

    if review is None:
        raise GeneralResumeServiceError(
            "Review not found.",
            status_code=404,
            code="review_not_found",
        )

    return review


def create_review(
    db: Session,
    *,
    current_user: User,
    resume_version_id: UUID,
    assessment_id: UUID,
    decisions: list[dict],
) -> GeneralResumeReview:
    """Record the user's decisions; if anything was approved, create a
    `Refined N` child version from the user's own text and recheck it.

    Idempotent per decision set (fingerprint + DB unique constraint).
    """
    user_id = current_user.id
    parent = _load_owned_version(
        db, user_id=user_id, resume_version_id=resume_version_id
    )

    assessment = (
        db.query(GeneralResumeAssessment)
        .filter(
            GeneralResumeAssessment.id == assessment_id,
            GeneralResumeAssessment.user_id == user_id,
            GeneralResumeAssessment.resume_version_id == parent.id,
        )
        .first()
    )

    if assessment is None:
        raise GeneralResumeServiceError(
            "Assessment not found.",
            status_code=404,
            code="assessment_not_found",
        )

    result = GeneralResumeAssessmentResult.model_validate(assessment.result)

    try:
        validated = validate_review_decisions(
            decisions=decisions,
            improvements_by_id={
                item.improvement_id: item for item in result.improvements
            },
        )
    except ReviewValidationError as exc:
        raise GeneralResumeServiceError(
            exc.message, status_code=422, code=exc.code
        ) from exc

    fingerprint = compute_review_fingerprint(
        assessment_id=str(assessment.id),
        parent_resume_version_id=str(parent.id),
        decisions=validated,
    )

    existing = _find_review(
        db, user_id=user_id, assessment_id=assessment.id, fingerprint=fingerprint
    )

    if existing is not None:
        return existing

    approved_count = sum(1 for d in validated if d.action == "approve")
    content = None

    if approved_count:
        try:
            content = build_refined_content(
                parent_content=parent.content_text,
                decisions=validated,
            )
        except ReviewValidationError as exc:
            raise GeneralResumeServiceError(
                exc.message, status_code=422, code=exc.code
            ) from exc

        if content.strip() == parent.content_text.strip():
            raise GeneralResumeServiceError(
                "The approved changes would not alter your resume.",
                status_code=422,
                code="no_change",
            )

        if not validate_resume_text(content).valid:
            raise GeneralResumeServiceError(
                "The approved changes would leave a resume that no longer "
                "passes validation.",
                status_code=422,
                code="invalid_result",
            )

        duplicate = (
            db.query(ResumeVersion)
            .join(ResumeVersion.resume)
            .filter(
                Resume.user_id == user_id,
                ResumeVersion.content_fingerprint
                == compute_content_fingerprint(content),
            )
            .first()
        )

        if duplicate is not None:
            raise GeneralResumeServiceError(
                f'This content already exists as version "{duplicate.name}".',
                status_code=422,
                code="duplicate_content",
            )

    savepoint = db.begin_nested()
    child = None

    if content is not None:
        existing_names = [
            row[0]
            for row in db.query(ResumeVersion.name)
            .filter(ResumeVersion.resume_id == parent.resume_id)
            .all()
        ]
        # The parent row is read, never written. The child never becomes
        # master automatically (Product Owner decision).
        child = ResumeVersion(
            resume_id=parent.resume_id,
            name=next_refined_version_name(existing_names),
            content_text=content,
            content_fingerprint=compute_content_fingerprint(content),
            original_filename=parent.original_filename,
            storage_path=None,
            parent_version_id=parent.id,
            source=VERSION_SOURCE,
            is_master=False,
        )
        db.add(child)
        db.flush()

    review = GeneralResumeReview(
        user_id=user_id,
        assessment_id=assessment.id,
        parent_resume_version_id=parent.id,
        child_resume_version_id=child.id if child else None,
        approval_fingerprint=fingerprint,
        engine_version=ENGINE_VERSION,
        approved_count=approved_count,
        rejected_count=len(validated) - approved_count,
        decisions=_decision_records(validated),
        recheck_status="pending" if child else "not_required",
    )
    db.add(review)

    try:
        db.flush()
    except IntegrityError:
        # A concurrent identical submission won; its version is the one
        # kept, and this attempt's child is rolled back with it.
        savepoint.rollback()
        winner = _find_review(
            db, user_id=user_id, assessment_id=assessment.id, fingerprint=fingerprint
        )

        if winner is not None:
            return winner

        raise

    db.commit()
    db.refresh(review)

    if child is None:
        return review

    return _run_recheck(db, current_user=current_user, review=review)


def _run_recheck(
    db: Session,
    *,
    current_user: User,
    review: GeneralResumeReview,
) -> GeneralResumeReview:
    """Assess the child version with the same pipeline. Runs only after
    the review and child are committed; every failure path leaves both
    intact and only updates the recheck fields."""
    review_id = review.id
    child_id = review.child_resume_version_id
    savepoint = db.begin_nested()

    try:
        recheck = assess_resume_version(
            db, user_id=current_user.id, resume_version_id=child_id
        )
    except Exception as exc:
        logger.error(
            "General Resume recheck failed for review %s (version %s): %s",
            review_id,
            child_id,
            exc,
        )

        if savepoint.is_active:
            savepoint.rollback()

        refreshed = db.get(GeneralResumeReview, review_id)

        if refreshed is None:
            raise

        refreshed.recheck_status = "failed"
        refreshed.recheck_error = (
            exc.message
            if isinstance(exc, GeneralResumeServiceError)
            else "The recheck could not be completed."
        )
        db.commit()
        db.refresh(refreshed)

        return refreshed

    if savepoint.is_active:
        savepoint.commit()

    review = db.get(GeneralResumeReview, review_id)
    review.recheck_assessment_id = recheck.id
    review.recheck_status = "complete"
    review.recheck_error = None
    db.commit()
    db.refresh(review)

    return review


def run_review_recheck(
    db: Session,
    *,
    current_user: User,
    review_id: UUID,
) -> GeneralResumeReview:
    """Retry a review's recheck. Never creates a version or re-applies
    decisions; a completed recheck is returned unchanged (its assessment
    is never re-pointed)."""
    review = get_review(db, user_id=current_user.id, review_id=review_id)

    if review.child_resume_version_id is None:
        if review.recheck_status == "not_required":
            return review

        raise GeneralResumeServiceError(
            "This review's version no longer exists.",
            status_code=409,
            code="version_missing",
        )

    if review.recheck_status == "complete" and review.recheck_assessment_id:
        return review

    return _run_recheck(db, current_user=current_user, review=review)
