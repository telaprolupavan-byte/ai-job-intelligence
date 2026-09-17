"""Gap Analysis & Job-Specific Suggestions orchestration service (AJI-015).

The database-touching layer between the /jobs router and the pure,
DB-free deterministic engine + validator modules — the same DB/pure-core
split `apps.api.services.job_intelligence.service` uses for Job
Intelligence and `apps.api.services.ats_alignment_service` uses for ATS
Alignment.

Source data (reused, never recreated): Gap Analysis never re-parses a
JD, never re-runs the resume analyzer, and never reimplements ATS
scoring. Every gap comes from an existing AJI-013 `AtsAlignmentResult` —
the canonical requirement-alignment source — obtained via
`apps.api.services.ats_alignment_service.calculate_ats_alignment()`,
which already resolves the ResumeVersion (with ownership enforcement),
obtains/generates the Job Intelligence snapshot, and is itself
idempotent (a cache hit is a single indexed read, no resume re-analysis,
no AI call). Gap Analysis is layered on top of that result, never
alongside or instead of it.

Versioning/idempotency: a Gap Analysis result is keyed by (user_id,
job_id, ats_alignment_id, analyzer_version, prompt_version).
`AtsAlignmentResult` is itself immutable/insert-only, so a cached Gap
Analysis result for this exact combination is valid indefinitely —
reused exactly like `AtsAlignmentResult`/`JobIntelligence` caching. A
changed resume version or JD produces a new, additional
`AtsAlignmentResult` (never a mutation), which in turn always produces a
new, additional Gap Analysis row; existing rows are never overwritten.

User isolation: every read/write here is always scoped to the requesting
user's own `user_id`, mirroring `AtsAlignmentResult`'s own isolation —
Gap Analysis is personalized (the same job can be analyzed against
different resumes/users).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.models import GapAnalysis, User
from apps.api.services.ats_alignment_service import (
    ATSAlignmentServiceError,
    calculate_ats_alignment,
)
from apps.api.services.gap_analysis.engine import select_gap_candidates
from apps.api.services.gap_analysis.interpreter import (
    GapAnalysisInterpreter,
    PROMPT_VERSION,
)
from apps.api.services.gap_analysis.providers import create_gap_analysis_provider
from apps.api.services.gap_analysis.providers.openai_provider import (
    GapAnalysisProviderError,
)
from apps.api.services.gap_analysis.validator import (
    GapAnalysisValidationError,
    build_gap_analysis_result,
)


ANALYSIS_VERSION = "1.0"
ANALYZER_VERSION = "1.0"

logger = logging.getLogger(__name__)


class GapAnalysisServiceError(RuntimeError):
    """Application-level error for Gap Analysis orchestration failures."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Read (never computes, never calls the AI provider)
# ---------------------------------------------------------------------------

def get_latest_gap_analysis(
    db: Session,
    *,
    user_id: UUID,
    job_id: UUID,
    resume_version_id: UUID | None = None,
) -> GapAnalysis | None:
    """
    Read-only lookup of the newest Gap Analysis result for this user and
    job (optionally pinned to one exact resume version). Never recomputes
    and never calls `calculate_ats_alignment()` or an AI provider.
    """
    query = db.query(GapAnalysis).filter(
        GapAnalysis.user_id == user_id,
        GapAnalysis.job_id == job_id,
    )

    if resume_version_id is not None:
        query = query.filter(GapAnalysis.resume_version_id == resume_version_id)

    return query.order_by(GapAnalysis.created_at.desc()).first()


# ---------------------------------------------------------------------------
# Create-or-reuse
# ---------------------------------------------------------------------------

def generate_gap_analysis(
    *,
    db: Session,
    current_user: User,
    job_id: UUID,
    resume_version_id: UUID | None = None,
) -> GapAnalysis:
    try:
        ats_record = calculate_ats_alignment(
            db=db,
            current_user=current_user,
            job_id=job_id,
            resume_version_id=resume_version_id,
        )
    except ATSAlignmentServiceError as exc:
        raise GapAnalysisServiceError(
            str(exc), status_code=exc.status_code
        ) from exc

    cached = (
        db.query(GapAnalysis)
        .filter(
            GapAnalysis.user_id == current_user.id,
            GapAnalysis.job_id == job_id,
            GapAnalysis.ats_alignment_id == ats_record.id,
            GapAnalysis.analyzer_version == ANALYZER_VERSION,
            GapAnalysis.prompt_version == PROMPT_VERSION,
        )
        .order_by(GapAnalysis.created_at.desc())
        .first()
    )

    if cached is not None:
        return cached

    candidates = select_gap_candidates(ats_record.result["requirement_results"])

    ai_semantics: dict | None = None
    model_provider: str | None = None
    model_name: str | None = None

    if candidates:
        try:
            provider = create_gap_analysis_provider()
            interpreter = GapAnalysisInterpreter(provider)
            interpretation = interpreter.analyze(
                gap_candidates=[
                    {
                        "requirement_id": candidate.requirement_id,
                        "requirement_type": candidate.requirement_type,
                        "requirement_text": candidate.requirement_text,
                        "status": candidate.status,
                        "jd_evidence": candidate.jd_evidence,
                        "resume_evidence": candidate.resume_evidence,
                        "required_suggestion_type": (
                            "ADD_IF_TRUE"
                            if candidate.status == "missing"
                            else "REPHRASE_EXISTING or HIGHLIGHT_EXISTING"
                        ),
                    }
                    for candidate in candidates
                ],
                job_context={"job_id": str(job_id)},
            )
            ai_semantics = interpretation.result
            model_provider = interpretation.provider
            model_name = interpretation.model
        except (GapAnalysisProviderError, ValueError, RuntimeError) as exc:
            # A failed AI call never blocks or corrupts the deterministic
            # result: every gap still gets a safe, template-generated
            # explanation and suggestion (see engine.py).
            logger.error(
                "Gap Analysis AI enrichment failed for job_id=%s, "
                "ats_alignment_id=%s: %s",
                job_id,
                ats_record.id,
                exc,
            )
            ai_semantics = None

    try:
        result = build_gap_analysis_result(
            analysis_version=ANALYSIS_VERSION,
            job_id=str(job_id),
            resume_version_id=str(ats_record.resume_version_id),
            ats_alignment_id=str(ats_record.id),
            candidates=candidates,
            ai_semantics=ai_semantics,
        )
    except GapAnalysisValidationError as exc:
        logger.error(
            "Gap Analysis validation failed for job_id=%s, "
            "ats_alignment_id=%s: %s",
            job_id,
            ats_record.id,
            exc,
        )
        raise GapAnalysisServiceError(
            "Unable to generate a valid Gap Analysis result.",
            status_code=503,
        ) from exc

    record = GapAnalysis(
        user_id=current_user.id,
        job_id=job_id,
        resume_version_id=ats_record.resume_version_id,
        job_intelligence_id=ats_record.job_intelligence_id,
        ats_alignment_id=ats_record.id,
        job_content_fingerprint=ats_record.job_content_fingerprint,
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=PROMPT_VERSION,
        model_provider=model_provider,
        model_name=model_name,
        # No gaps at all is a fully "complete" result (there was nothing
        # for the AI stage to enrich) — "partial" only ever means the AI
        # enrichment call itself failed while there were gaps to enrich.
        generation_status=(
            "complete" if not candidates or ai_semantics is not None else "partial"
        ),
        must_have_gap_count=result.must_have_gap_count,
        preferred_gap_count=result.preferred_gap_count,
        result=result.model_dump(mode="json"),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
