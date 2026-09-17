"""Job Intelligence orchestration service (AJI-012).

This is the database-touching layer between the /jobs router and the
pure, DB-free deterministic extraction + validator modules — the same
DB/pure-core split used by `apps.api.services.resume_ai.service` for
Resume Intelligence and `apps.api.services.job_match_service` for Job
Match.

Idempotency: a Job Intelligence snapshot is keyed by
(job_id, content_fingerprint, analyzer_version, prompt_version). Viewing
the same job repeatedly, or recomputing it when nothing about the job's
observable content or the analyzer/prompt pipeline has changed, reuses
the existing snapshot instead of re-running extraction or calling the AI
provider again — mirroring `ResumeAIAnalysis`'s caching pattern. A
changed JD (different fingerprint) or a bumped analyzer/prompt version
always produces a new, additional snapshot; existing snapshots are never
overwritten (insert-only).

Failure handling: if deterministic extraction or the validator itself
fails, no snapshot is persisted at all — a request-time error is raised
instead of writing malformed data (AJI-012 section 20/28). If only the
AI semantic decoding stage fails (provider error, timeout, invalid
output), the deterministically-extracted fields are still persisted as
a "partial" snapshot rather than being discarded, since they are real,
evidence-backed data independent of the AI call.
"""

from __future__ import annotations

import hashlib
import logging
import re
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.models import Job, JobIntelligence
from apps.api.services.job_intelligence.deterministic import (
    RawJobDescription,
    extract_deterministic,
)
from apps.api.services.job_intelligence.interpreter import (
    JobIntelligenceInterpreter,
    PROMPT_VERSION,
)
from apps.api.services.job_intelligence.providers import (
    create_job_intelligence_provider,
)
from apps.api.services.job_intelligence.providers.openai_provider import (
    JobIntelligenceProviderError,
)
from apps.api.services.job_intelligence.validator import (
    JobIntelligenceValidationError,
    build_job_intelligence_result,
)


ANALYSIS_VERSION = "1.0"
ANALYZER_VERSION = "1.0"

logger = logging.getLogger(__name__)


class JobIntelligenceServiceError(RuntimeError):
    """Application-level error for Job Intelligence orchestration failures."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def _raw_job_description(job: Job) -> RawJobDescription:
    return RawJobDescription(
        title=job.title,
        description=job.description,
        requirements=job.requirements,
        responsibilities=job.responsibilities,
        location=job.location,
        country=job.country,
        remote_type=job.remote_type,
        employment_type=job.employment_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        contract_duration=job.contract_duration,
        contract_worker_type=job.contract_worker_type,
    )


def _raw_jd_text(job: Job) -> str:
    return "\n".join(
        part
        for part in [
            job.title,
            job.location,
            job.description,
            job.requirements,
            job.responsibilities,
        ]
        if part
    )


def _raw_jd_snapshot(job: Job) -> dict:
    return {
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "responsibilities": job.responsibilities,
        "location": job.location,
        "country": job.country,
        "remote_type": job.remote_type,
        "employment_type": job.employment_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "contract_duration": job.contract_duration,
        "contract_worker_type": job.contract_worker_type,
        "source": job.source,
        "source_url": job.source_url,
        "application_url": job.application_url,
    }


def compute_job_content_fingerprint(job: Job) -> str:
    """
    Deterministic content identity for a Job's observable JD fields.

    Two jobs (or the same job at two points in time) with identical
    normalized content always produce the same fingerprint; any change
    to a field that feeds extraction changes it. Used to decide whether
    an existing Job Intelligence snapshot may be reused or whether a new
    one is required (AJI-012 sections 16/17).
    """
    parts = [
        job.title or "",
        job.description or "",
        job.requirements or "",
        job.responsibilities or "",
        job.location or "",
        job.country or "",
        job.remote_type or "",
        job.employment_type or "",
        "" if job.salary_min is None else repr(job.salary_min),
        "" if job.salary_max is None else repr(job.salary_max),
        job.salary_currency or "",
        job.contract_duration or "",
        job.contract_worker_type or "",
    ]

    normalized = "\n".join(
        re.sub(r"\s+", " ", part).strip().lower() for part in parts
    )

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_latest_job_intelligence(
    db: Session, *, job_id: UUID
) -> JobIntelligence | None:
    """Read-only lookup of the newest snapshot; never recomputes."""
    return (
        db.query(JobIntelligence)
        .filter(JobIntelligence.job_id == job_id)
        .order_by(JobIntelligence.created_at.desc())
        .first()
    )


def generate_job_intelligence(
    db: Session, *, job_id: UUID
) -> JobIntelligence:
    job = db.query(Job).filter(Job.id == job_id).first()

    if job is None:
        raise JobIntelligenceServiceError("Job not found", status_code=404)

    fingerprint = compute_job_content_fingerprint(job)

    cached = (
        db.query(JobIntelligence)
        .filter(
            JobIntelligence.job_id == job_id,
            JobIntelligence.content_fingerprint == fingerprint,
            JobIntelligence.analyzer_version == ANALYZER_VERSION,
            JobIntelligence.prompt_version == PROMPT_VERSION,
        )
        .order_by(JobIntelligence.created_at.desc())
        .first()
    )

    if cached is not None:
        return cached

    raw = _raw_job_description(job)

    try:
        deterministic = extract_deterministic(raw)
    except Exception as exc:
        logger.error(
            "Deterministic Job Intelligence extraction failed for "
            "job_id=%s: %s",
            job_id,
            exc,
        )
        raise JobIntelligenceServiceError(
            "Unable to extract Job Intelligence for this job.",
            status_code=503,
        ) from exc

    raw_text = _raw_jd_text(job)

    ai_semantics: dict | None = None
    model_provider: str | None = None
    model_name: str | None = None

    try:
        provider = create_job_intelligence_provider()
        interpreter = JobIntelligenceInterpreter(provider)
        interpretation = interpreter.analyze(
            raw_jd_text=raw_text,
            deterministic_context={
                "employment_type": deterministic.employment.employment_type,
                "seniority": deterministic.seniority,
                "required_skills": [
                    item.canonical_skill
                    for item in deterministic.required_skills
                ],
                "preferred_skills": [
                    item.canonical_skill
                    for item in deterministic.preferred_skills
                ],
            },
        )
        ai_semantics = interpretation.result
        model_provider = interpretation.provider
        model_name = interpretation.model
    except (JobIntelligenceProviderError, ValueError, RuntimeError) as exc:
        # A failed AI call never blocks or corrupts the deterministic
        # result: it degrades to a "partial" snapshot instead.
        logger.error(
            "Job Intelligence AI semantics failed for job_id=%s: %s",
            job_id,
            exc,
        )
        ai_semantics = None

    try:
        result = build_job_intelligence_result(
            job_id=str(job_id),
            analysis_version=ANALYSIS_VERSION,
            raw_title=job.title,
            raw_text=raw_text,
            deterministic=deterministic,
            ai_semantics=ai_semantics,
        )
    except JobIntelligenceValidationError as exc:
        logger.error(
            "Job Intelligence validation failed for job_id=%s: %s",
            job_id,
            exc,
        )
        raise JobIntelligenceServiceError(
            "Unable to generate a valid Job Intelligence result.",
            status_code=503,
        ) from exc

    record = JobIntelligence(
        job_id=job.id,
        content_fingerprint=fingerprint,
        raw_jd_snapshot=_raw_jd_snapshot(job),
        source=job.source,
        source_url=job.source_url,
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=PROMPT_VERSION,
        model_provider=model_provider,
        model_name=model_name,
        extraction_status="complete" if ai_semantics is not None else "partial",
        structured_intelligence=result.model_dump(mode="json"),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
