"""Requirement Intelligence persistence orchestration (AJI-020B).

This is the database-touching layer between the `/jobs` router and the
AJI-020A pipeline (`apps.api.services.requirement_intelligence.service`,
`.deterministic`, `.contracts`, etc. — all locked/unmodified by this
ticket): the same DB/pure-core split `apps.api.services.job_intelligence.
service` and `apps.api.services.ats_alignment_service` already use for
their own domains. AJI-020A's own `service.py` stays a pure, DB-free
function (`build_requirement_intelligence()`); this module only adds
persistence/identity/idempotency around it and never re-implements or
overrides any of its extraction/validation logic.

Personalization (AJI-020B product decision): unlike `JobIntelligence`
(shared, job-scoped, no `user_id`), a `RequirementIntelligence` row is
tied to both `user_id` and `job_id` — a user must never be able to read
another user's snapshot (see apps/api/models.py's `RequirementIntelligence`
docstring and docs/ARCHITECTURE.md's AJI-020B section for why).

Idempotency key: `(user_id, job_id, content_fingerprint, analyzer_version,
prompt_version, model_provider, model_name)` — deliberately wider than
`JobIntelligence`'s `(job_id, content_fingerprint, analyzer_version,
prompt_version)`, per the AJI-020B ticket's explicit instruction that a
changed "model/provider configuration" must also be able to produce a
new snapshot (sections 6/11). Since determining a provider requires no
network call (it is read straight off `apps.api.config.settings`, the
same settings `providers.factory.create_requirement_intelligence_provider`
itself reads — see `_prospective_model_identity` below), this can be
computed *before* invoking AJI-020A's pipeline, so a cache hit skips the
AI call entirely (no "unnecessary AI call" per section 11). A side effect
worth knowing (see docs/ARCHITECTURE.md's AJI-020B "Known limitations"):
a "partial" row (AI stage failed/unavailable) always has
`model_provider`/`model_name = NULL`, and Postgres treats `NULL` as
never equal to `NULL` — so this key can never match an existing partial
row. This is a deliberate trade-off: every request self-heals (it always
retries the AI stage rather than permanently serving a stale partial
result once cached, unlike `JobIntelligence`'s narrower key), at the cost
of one additional partial row per repeated request while the AI provider
stays unavailable. Nothing in this ticket's scope calls for smoothing
that further (no request-level rate limiting/caching layer is in scope
here — see AJI-020B section 11's "no Redis" instruction).
"""

from __future__ import annotations

import hashlib
import logging
import re
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import Job, RequirementIntelligence
from apps.api.services.requirement_intelligence.deterministic import (
    RawRequirementSource,
)
# Imported as a module, not `from ... import ANALYZER_VERSION`/
# `PROMPT_VERSION`: `build_requirement_intelligence()` (below) reads
# those two names as its own module globals at *call* time, so a
# `from...import` copy taken once at import time would silently drift
# out of sync with whatever that function actually stamps onto a result
# if the source module's attribute is ever changed after import (e.g. a
# test simulating a version bump via `monkeypatch.setattr(...)`, the
# same technique `job_intelligence`'s own versioning tests use).
# Referencing the module and reading `.ANALYZER_VERSION`/
# `.PROMPT_VERSION` live keeps this module's idempotency-lookup key and
# AJI-020A's own stamped result permanently reading the same single
# source of truth.
from apps.api.services.requirement_intelligence import (
    service as requirement_intelligence_service,
)
from apps.api.services.requirement_intelligence.service import (
    RequirementIntelligenceServiceError,
    build_requirement_intelligence,
)


logger = logging.getLogger(__name__)


class RequirementIntelligencePersistenceError(RuntimeError):
    """Application-level error for Requirement Intelligence persistence
    orchestration failures (job not found, or AJI-020A itself failing)."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def _raw_requirement_source(job: Job) -> RawRequirementSource:
    return RawRequirementSource(
        title=job.title,
        description=job.description,
        requirements=job.requirements,
        responsibilities=job.responsibilities,
    )


def _raw_jd_snapshot(job: Job) -> dict:
    return {
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "responsibilities": job.responsibilities,
    }


def compute_requirement_content_fingerprint(job: Job) -> str:
    """
    Deterministic content identity for exactly the `Job` fields AJI-020A's
    extraction pipeline reads (title/description/requirements/
    responsibilities — see `deterministic.RawRequirementSource`).

    Deliberately narrower than `job_intelligence.service.
    compute_job_content_fingerprint` (which additionally hashes location/
    salary/employment-type/etc.): those fields are never read by this
    pipeline, so including them would change the fingerprint — and so
    create an unnecessary "new snapshot" — on a Job edit that could not
    possibly change this pipeline's output (AJI-020B section 5: "must
    ... change when the relevant analyzed content changes", not any
    content). Uses the same canonicalization approach as
    `compute_job_content_fingerprint` (whitespace-collapsed, lowercased,
    newline-joined, SHA-256) for consistency with the established
    convention — no timestamps, random values, or model-generated text
    ever feed it.
    """
    parts = [
        job.title or "",
        job.description or "",
        job.requirements or "",
        job.responsibilities or "",
    ]

    normalized = "\n".join(
        re.sub(r"\s+", " ", part).strip().lower() for part in parts
    )

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _prospective_model_identity() -> tuple[str | None, str | None]:
    """The `(model_provider, model_name)` AJI-020A's own provider factory
    would use right now, read directly from `apps.api.config.settings`
    (the same settings `providers.factory.
    create_requirement_intelligence_provider` reads) — no network call,
    and no provider-specific import, keeping this module
    provider-independent (AJI-020B section 10).
    """
    provider = (settings.ai_provider or "").lower().strip()

    if not provider:
        return None, None

    return provider, settings.ai_model


def get_latest_requirement_intelligence(
    db: Session, *, user_id: UUID, job_id: UUID
) -> RequirementIntelligence | None:
    """Read-only lookup of the newest snapshot for this user and job;
    never recomputes or calls the AI provider on a read."""
    return (
        db.query(RequirementIntelligence)
        .filter(
            RequirementIntelligence.user_id == user_id,
            RequirementIntelligence.job_id == job_id,
        )
        .order_by(RequirementIntelligence.created_at.desc())
        .first()
    )


def generate_requirement_intelligence(
    db: Session, *, user_id: UUID, job_id: UUID
) -> RequirementIntelligence:
    """
    Compute-or-reuse the Requirement Intelligence snapshot for this exact
    `(user_id, job_id)`, idempotent on `(content_fingerprint,
    analyzer_version, prompt_version, model_provider, model_name)` — see
    the module docstring for the key's exact rationale.

    `user_id`/`job_id` are always the server-resolved authenticated
    user and a job looked up by its own id — never taken from client-
    supplied request data (AJI-020B section 13: "Do not trust
    client-provided user_id ... Server-side values must be
    authoritative").
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if job is None:
        raise RequirementIntelligencePersistenceError(
            "Job not found", status_code=404
        )

    fingerprint = compute_requirement_content_fingerprint(job)
    prospective_provider, prospective_model = _prospective_model_identity()

    cached = (
        db.query(RequirementIntelligence)
        .filter(
            RequirementIntelligence.user_id == user_id,
            RequirementIntelligence.job_id == job_id,
            RequirementIntelligence.content_fingerprint == fingerprint,
            RequirementIntelligence.analyzer_version
            == requirement_intelligence_service.ANALYZER_VERSION,
            RequirementIntelligence.prompt_version
            == requirement_intelligence_service.PROMPT_VERSION,
            RequirementIntelligence.model_provider == prospective_provider,
            RequirementIntelligence.model_name == prospective_model,
        )
        .order_by(RequirementIntelligence.created_at.desc())
        .first()
    )

    if cached is not None:
        return cached

    raw = _raw_requirement_source(job)

    try:
        result = build_requirement_intelligence(raw, source_id=str(job_id))
    except RequirementIntelligenceServiceError as exc:
        logger.error(
            "Requirement Intelligence generation failed for "
            "user_id=%s job_id=%s: %s",
            user_id,
            job_id,
            exc,
        )
        raise RequirementIntelligencePersistenceError(
            str(exc), status_code=exc.status_code
        ) from exc

    record = RequirementIntelligence(
        user_id=user_id,
        job_id=job.id,
        content_fingerprint=fingerprint,
        raw_jd_snapshot=_raw_jd_snapshot(job),
        analysis_version=result.analysis_version,
        analyzer_version=result.analyzer_version,
        prompt_version=result.prompt_version,
        model_provider=result.model_provider,
        model_name=result.model_name,
        extraction_status=result.extraction_status,
        structured_intelligence=result.model_dump(mode="json"),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
