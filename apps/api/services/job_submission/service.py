"""User Job Submission orchestration (AJI-022).

Turns content a user pasted into a private `Job` and runs the *existing*
intelligence pipelines on it - no second Job Intelligence engine:

1. The raw paste is stored verbatim on `Job.raw_submitted_content`, and
   its deterministic section split (`normalizer.py`) feeds the
   `description`/`requirements`/`responsibilities` columns every existing
   pipeline already reads.
2. The job is owned by the submitting user (`submitted_by_user_id`), with
   `source = "user_submitted"`. `apps/api/services/job_access.py` keeps it
   invisible to everyone else.
3. AJI-012 Job Intelligence and AJI-020A/B Requirement Intelligence run
   synchronously through their existing `generate_*` functions, with
   their existing validators, evidence-substring checks, prompt-injection
   handling, and snapshot/idempotency behavior unchanged.

Idempotency: the job row is keyed by an identity fingerprint over (user,
title, company, content). Resubmitting the same content - including a
"Try again" after an analysis failure - reuses the same job instead of
creating a duplicate, and the pipelines' own caches then reuse any
snapshot that already succeeded.

A failed analysis never discards the submission: the job is committed
before analysis starts, so the paste is never lost and a retry picks up
the same row.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models import (
    Company,
    Job,
    JobIntelligence,
    RequirementIntelligence,
    User,
)
from apps.api.services.job_intelligence.service import (
    JobIntelligenceServiceError,
    generate_job_intelligence,
)
from apps.api.services.job_submission.normalizer import (
    normalize_job_content,
    resolve_title,
)
from apps.api.services.requirement_intelligence.contracts import (
    PromptInjectionSignal,
)
from apps.api.services.requirement_intelligence.deterministic import (
    detect_prompt_injection_signals,
)
from apps.api.services.requirement_intelligence.persistence_service import (
    RequirementIntelligencePersistenceError,
    generate_requirement_intelligence,
)
from services.job_discovery.normalizer import normalize_text
from services.job_discovery.persistence import (
    normalize_company_name,
    utcnow_naive,
)


SUBMISSION_SOURCE = "user_submitted"


class JobSubmissionServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        job_id: UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        # Set once the job row exists, so the caller can still point the
        # user at their (saved) submission when analysis fails.
        self.job_id = job_id


@dataclass
class JobSubmissionResult:
    job: Job
    job_intelligence: JobIntelligence
    requirement_intelligence: RequirementIntelligence
    injection_signals: list[PromptInjectionSignal] = field(
        default_factory=list
    )


def compute_submission_fingerprint(
    *,
    user_id: UUID,
    title: str,
    company: str | None,
    content: str,
) -> str:
    parts = [str(user_id), title, company or "", content]
    normalized = "\n".join(
        re.sub(r"\s+", " ", part).strip().lower() for part in parts
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _get_or_create_company(db: Session, name: str) -> Company:
    """Same lookup rule job discovery uses, so a submitted "Acme Inc."
    and a discovered one share a single `Company` row."""
    normalized_name = normalize_company_name(name)

    company = db.scalar(
        select(Company).where(Company.normalized_name == normalized_name)
    )

    if company is not None:
        return company

    company = Company(name=normalize_text(name), normalized_name=normalized_name)
    db.add(company)
    db.flush()

    return company


def _find_or_create_job(
    db: Session,
    *,
    current_user: User,
    title: str,
    company_name: str | None,
    content: str,
) -> Job:
    fingerprint = compute_submission_fingerprint(
        user_id=current_user.id,
        title=title,
        company=company_name,
        content=content,
    )

    existing = (
        db.query(Job)
        .filter(
            Job.submitted_by_user_id == current_user.id,
            Job.source == SUBMISSION_SOURCE,
            Job.identity_fingerprint == fingerprint,
        )
        .first()
    )

    if existing is not None:
        return existing

    normalized = normalize_job_content(content)
    company = (
        _get_or_create_company(db, company_name) if company_name else None
    )
    now = utcnow_naive()

    job = Job(
        company_id=company.id if company else None,
        title=title,
        # Unknown for pasted content - stored empty rather than the
        # column's "USA" default, which would be an invented fact.
        country="",
        description=normalized.description,
        requirements=normalized.requirements,
        responsibilities=normalized.responsibilities,
        raw_submitted_content=content,
        source=SUBMISSION_SOURCE,
        submitted_by_user_id=current_user.id,
        identity_fingerprint=fingerprint,
        first_seen_at=now,
        last_seen_at=now,
        is_active=True,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def submit_job(
    db: Session,
    *,
    current_user: User,
    content: str,
    title: str | None = None,
    company: str | None = None,
) -> JobSubmissionResult:
    if not content or not content.strip():
        raise JobSubmissionServiceError(
            "Paste the job description to continue.", status_code=422
        )

    resolved_title = resolve_title(title, content)
    company_name = company.strip() if company and company.strip() else None

    job = _find_or_create_job(
        db,
        current_user=current_user,
        title=resolved_title,
        company_name=company_name,
        content=content,
    )

    try:
        job_intelligence = generate_job_intelligence(db, job_id=job.id)
        requirement_intelligence = generate_requirement_intelligence(
            db, user_id=current_user.id, job_id=job.id
        )
    except (
        JobIntelligenceServiceError,
        RequirementIntelligencePersistenceError,
    ) as exc:
        raise JobSubmissionServiceError(
            "NERO couldn't analyze this job content. Review the text and "
            "try again.",
            status_code=exc.status_code if exc.status_code >= 500 else 503,
            job_id=job.id,
        ) from exc

    # Diagnostic only, like AJI-020A's own SecurityDiagnostics: scans
    # everything the user supplied (title and company included, which
    # Requirement Intelligence's own scan does not cover). Nothing is
    # stripped or blocked - the structural evidence-substring check is
    # the safety boundary.
    injection_signals = detect_prompt_injection_signals(
        "\n".join(part for part in [title, company, content] if part)
    )

    return JobSubmissionResult(
        job=job,
        job_intelligence=job_intelligence,
        requirement_intelligence=requirement_intelligence,
        injection_signals=injection_signals,
    )
