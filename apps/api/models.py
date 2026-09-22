import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    preferences: Mapped["Preference | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PasswordResetToken(Base):
    """A single-use, expiring password reset token (AUTH-XXX).

    Only the SHA-256 hash of the token is stored, mirroring how
    `password_hash` never stores the raw password — the raw token is
    handed to the user via the reset-link email and never persisted.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
    )

    years_experience: Mapped[float | None] = mapped_column(
        Float,
    )

    target_titles: Mapped[list | None] = mapped_column(
        JSONB,
    )

    user: Mapped["User"] = relationship(
        back_populates="profile",
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    filename: Mapped[str] = mapped_column(
        String(255),
    )

    original_text: Mapped[str | None] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    user: Mapped["User"] = relationship(
        back_populates="resumes",
    )

    versions: Mapped[list["ResumeVersion"]] = relationship(
        back_populates="resume",
        cascade="all, delete-orphan",
    )


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    content_text: Mapped[str] = mapped_column(
        Text,
    )

    content_fingerprint: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
    )

    # Nullable since AJI-021: an uploaded version always has a stored
    # file, but a version created from approved Resume Improvement
    # suggestions is generated from its parent's text and has no source
    # document on disk. `GET /resumes/versions/{id}/file` 404s for those
    # rather than inventing a file. Existing rows are unaffected (the
    # column is only widened).
    storage_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # AJI-021 lineage: the exact ResumeVersion this one was derived from.
    # NULL for every uploaded version (including every row that existed
    # before this column). A child version NEVER replaces or mutates its
    # parent - the parent row, its text, its file, and its `is_master`
    # flag are all left exactly as they were.
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # "upload" (the user uploaded a document) or "improvement" (generated
    # by AJI-021 from user-approved, user-authored improvement content).
    # Never inferred from `parent_version_id` being set, so provenance
    # stays legible even if a parent row is later deleted.
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="upload",
        server_default="upload",
    )

    is_master: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    resume: Mapped["Resume"] = relationship(
        back_populates="versions",
    )


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )

    employment_types: Mapped[list | None] = mapped_column(
        JSONB,
    )

    locations: Mapped[list | None] = mapped_column(
        JSONB,
    )

    remote_preference: Mapped[str | None] = mapped_column(
        String(50),
    )

    target_titles: Mapped[list | None] = mapped_column(
        JSONB,
    )

    minimum_salary: Mapped[float | None] = mapped_column(
        Float,
    )

    minimum_hourly_rate: Mapped[float | None] = mapped_column(
        Float,
    )

    # --- Hard eligibility fields (AJI-011) ---
    #
    # `employment_types`, `locations`, and `remote_preference` above are
    # dual-purpose: Job Match continues to use them as soft scoring
    # inputs (unchanged), while the Hard Eligibility engine
    # (services.eligibility) treats a non-empty/non-null value as an
    # explicit hard restriction. The fields below have no soft-preference
    # role — they exist only to express hard eligibility requirements
    # that don't otherwise fit an existing field. See
    # docs/ARCHITECTURE.md for the full hard-vs-soft rationale.

    excluded_locations: Mapped[list | None] = mapped_column(
        JSONB,
    )

    # Work authorization: intentionally minimal. These represent only
    # the user's own declared sponsorship/citizenship/clearance
    # situation for the purpose of comparing against a job's observable
    # requirements — never an immigration/legal determination, and never
    # inferred from any other profile field. None means "unspecified"
    # (the corresponding hard check is skipped, not assumed).
    requires_sponsorship: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    is_us_citizen: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    has_security_clearance: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    # Experience is a hard constraint only when the user explicitly
    # opts in here; otherwise it never excludes a job (see
    # services/eligibility/engine.py::_check_experience).
    enforce_minimum_experience: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    user: Mapped["User"] = relationship(
        back_populates="preferences",
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    normalized_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(500),
    )

    jobs: Mapped[list["Job"]] = relationship(
        back_populates="company",
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
    )

    title: Mapped[str] = mapped_column(
        String(500),
    )

    location: Mapped[str | None] = mapped_column(
        String(500),
    )

    country: Mapped[str] = mapped_column(
        String(100),
        default="USA",
    )

    remote_type: Mapped[str | None] = mapped_column(
        String(50),
    )

    employment_type: Mapped[str | None] = mapped_column(
        String(50),
    )

    salary_min: Mapped[float | None] = mapped_column(
        Float,
    )

    salary_max: Mapped[float | None] = mapped_column(
        Float,
    )

    salary_currency: Mapped[str | None] = mapped_column(
        String(10),
    )

    contract_duration: Mapped[str | None] = mapped_column(
        String(100),
    )

    contract_worker_type: Mapped[str | None] = mapped_column(
        String(50),
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    requirements: Mapped[str | None] = mapped_column(
        Text,
    )

    responsibilities: Mapped[str | None] = mapped_column(
        Text,
    )

    posting_date: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    source: Mapped[str] = mapped_column(
        String(100),
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
    )

    application_url: Mapped[str | None] = mapped_column(
        String(1000),
    )

    external_job_id: Mapped[str | None] = mapped_column(
        String(255),
    )

    identity_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # AJI-022: NULL = a discovered job, shared with every user (the
    # original meaning of every existing row). A user id = a job that
    # user pasted in themselves; it is private to them and every per-job
    # endpoint 404s for anyone else (see apps/api/services/job_access.py).
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # AJI-022: the user's pasted job content exactly as submitted. The
    # description/requirements/responsibilities columns hold the
    # deterministic section split of it (the inputs Job Intelligence
    # reads), which cannot reproduce the original ordering on its own.
    # Always NULL for discovered jobs.
    raw_submitted_content: Mapped[str | None] = mapped_column(
        Text,
    )

    company: Mapped["Company | None"] = relationship(
        back_populates="jobs",
    )

    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_job_id",
            name="uq_job_source_external_id",
        ),
    )


class DiscoveryRun(Base):
    """Observability record for one invocation of the Job Discovery
    pipeline (POST /internal/job-discovery/run). Append-only - a run is
    inserted when it starts and updated once when it finishes, never
    deleted, so operators have an audit trail of what discovery actually
    did without needing to grep application logs."""

    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source: Mapped[str] = mapped_column(
        String(100),
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="running",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    fetched_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    inserted_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    updated_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    rejected_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(1000),
    )


class SavedJob(Base):
    """A user's application-tracking record for one job.

    This is the single row that carries a job from "saved" through the
    application pipeline (see ApplicationStatusEvent for the append-only
    history of every status it has passed through). One row per
    (user, job) - the unique constraint below is what makes "save" an
    idempotent action and prevents a duplicate tracking record for the
    same job.
    """

    __tablename__ = "saved_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="saved",
    )

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    job: Mapped["Job"] = relationship()

    status_events: Mapped[list["ApplicationStatusEvent"]] = relationship(
        back_populates="saved_job",
        order_by="ApplicationStatusEvent.created_at",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "job_id",
            name="uq_saved_job_user_job",
        ),
    )


class ApplicationStatusEvent(Base):
    """Append-only history of every status an application has passed
    through, so the Application Detail view can show a real timeline
    instead of only the current status. Never updated or deleted - a
    status change always adds a new row."""

    __tablename__ = "application_status_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    saved_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("saved_jobs.id", ondelete="CASCADE"),
    )

    status: Mapped[str] = mapped_column(
        String(50),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    saved_job: Mapped["SavedJob"] = relationship(
        back_populates="status_events",
    )


class ResumeAIAnalysis(Base):
    __tablename__ = "resume_ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    analysis_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    analyzer_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    analysis_result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class JobIntelligence(Base):
    """A single versioned Job Intelligence snapshot (AJI-012).

    Insert-only, like `ResumeAIAnalysis`: a new row is created whenever the
    job's observable content (`content_fingerprint`) or the
    analyzer/prompt pipeline version changes. Historical snapshots are
    never overwritten, so past ATS/Match analysis built on an older
    snapshot stays stable even if the live job posting is edited later.

    This table is intentionally shared, job-scoped data (no `user_id`):
    it answers "what does this job require?", not anything
    user-specific. Personalized data (eligibility, Job Match, ATS
    Alignment) must never be stored here — see docs/ARCHITECTURE.md.
    """

    __tablename__ = "job_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # A snapshot of the exact observable job fields this analysis was
    # computed from, captured at analysis time. Preserved independently
    # of the live `Job` row so a later edit/rediscovery of the job never
    # silently changes what a historical snapshot says it analyzed.
    raw_jd_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # See docs/ARCHITECTURE.md's "Analysis/scoring versioning convention"
    # (AJI-011). Job Intelligence is AI-derived (deterministic extraction
    # feeds a schema-constrained AI semantic decoding stage), so it
    # follows the analysis/analyzer/prompt + model_provider/model_name
    # convention, like `ResumeAIAnalysis`.
    analysis_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    analyzer_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # "complete" (deterministic + AI semantics both succeeded) or
    # "partial" (the AI semantic decoding stage failed/was unavailable,
    # so only deterministically-extracted fields are populated). Never
    # "failed" — a failed extraction is not persisted at all.
    extraction_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="complete",
    )

    structured_intelligence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class RequirementIntelligence(Base):
    """A single versioned Requirement Intelligence snapshot (AJI-020B),
    persisting the AJI-020A `RequirementIntelligenceResult` contract
    (`apps.api.services.requirement_intelligence.contracts`) produced by
    `apps.api.services.requirement_intelligence.persistence_service`.

    Insert-only, like `JobIntelligence`/`AtsAlignmentResult`/
    `GapAnalysis` (see "Analysis/scoring versioning convention" above): a
    new row is created whenever the analyzed job content
    (`content_fingerprint`), the analyzer/prompt pipeline version, or the
    configured AI provider/model changes. Historical snapshots are never
    overwritten or mutated — `structured_intelligence` is the complete,
    lossless AJI-020A result exactly as validated by that module; this
    table adds persistence/identity around it and never re-derives or
    edits any part of it.

    Unlike `JobIntelligence` (shared, job-scoped, no `user_id`), this
    table is personalized (has a `user_id`), per the AJI-020B product
    decision: a user must never be able to read another user's snapshot.
    The requirement *content* itself does not vary by user (AJI-020A
    never looks at resume/user data), but the persisted snapshot's
    access is still scoped like `AtsAlignmentResult`/`GapAnalysis` — see
    docs/ARCHITECTURE.md's AJI-020B section for why.
    """

    __tablename__ = "requirement_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Deterministic content identity, scoped to exactly the `Job` fields
    # AJI-020A's extraction pipeline reads (title/description/
    # requirements/responsibilities — see
    # persistence_service.compute_requirement_content_fingerprint).
    # Deliberately a *different* fingerprint from `JobIntelligence.
    # content_fingerprint`, which additionally covers location/salary/
    # employment-type fields AJI-020A's pipeline never reads — hashing
    # those here would create a new "snapshot" on an edit that could not
    # possibly change this pipeline's output.
    content_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # A snapshot of the exact Job fields this analysis was computed from,
    # captured at analysis time — independent of the live `Job` row, so a
    # later edit/rediscovery of the job never silently changes what a
    # historical snapshot says it analyzed. Mirrors
    # `JobIntelligence.raw_jd_snapshot`.
    raw_jd_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # See docs/ARCHITECTURE.md's "Analysis/scoring versioning convention"
    # — copied verbatim from the AJI-020A result, never recomputed here,
    # so historical rows keep whatever version produced them even after
    # AJI-020A's own constants are bumped later.
    analysis_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    analyzer_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # "complete" (deterministic + AI semantics both succeeded) or
    # "partial" (the AI semantic decoding stage failed/was unavailable).
    # Never "failed" — a failed extraction is not persisted at all. Same
    # convention as `JobIntelligence.extraction_status`.
    extraction_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="complete",
    )

    # The complete, validated AJI-020A `RequirementIntelligenceResult`
    # (model_dump(mode="json")) — persisted losslessly, not decomposed
    # into separate tables (see docs/ARCHITECTURE.md's AJI-020B section
    # for why: it is already a single structured, closed-schema contract,
    # and every other AI-derived artifact in this system persists its
    # full contract the same way).
    structured_intelligence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Defensive backstop against a concurrent double-insert of the
        # exact same identity; the primary idempotency mechanism is the
        # look-up-before-insert in
        # persistence_service.generate_requirement_intelligence (see its
        # docstring for why `model_provider`/`model_name` are part of
        # this key, unlike `JobIntelligence`'s narrower one). Postgres
        # treats NULL as distinct from NULL, so this does not block
        # multiple "partial" rows (model_provider/model_name both NULL)
        # from coexisting — acceptable, since a partial row already
        # represents a failed AI attempt, and the application-level
        # lookup is what actually prevents redundant work within a
        # single request.
        UniqueConstraint(
            "user_id",
            "job_id",
            "content_fingerprint",
            "analyzer_version",
            "prompt_version",
            "model_provider",
            "model_name",
            name="uq_requirement_intelligence_identity",
        ),
    )


class JobEligibilityResult(Base):
    """The persisted Hard Eligibility snapshot for one (user, job) pair
    (AJI-011).

    Unlike `JobMatchResult`/`JobIntelligence`/`ResumeAIAnalysis` (insert-
    only history, kept so a past AI-derived analysis stays stable even if
    later recomputed), this table is upsert-latest: one row per
    `(user_id, job_id)`, overwritten in place whenever eligibility is
    (re)evaluated. Hard Eligibility is a deterministic pre-filter over
    live, mutable `Preference`/`Profile`/`Job` data with no AI cost to
    recompute, so a future consumer (AJI-012/AJI-013) only ever wants the
    *current* status ("is this job eligible for this user right now?"),
    never a historical trail of past evaluations — see
    docs/ARCHITECTURE.md for the full rationale.
    """

    __tablename__ = "job_eligibility_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    engine_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # The full structured result: checks (constraint/status/reason),
    # failed_constraints, unknown_constraints, reasons — see
    # services/eligibility/contracts.py::EligibilityResult.
    result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "job_id",
            name="uq_job_eligibility_result_user_job",
        ),
    )


class JobMatchResult(Base):
    """A single Job Match Score (existing; AJI-014 reconciled its job-side
    requirement source with AJI-012 Job Intelligence instead of the
    orchestration layer re-parsing raw JD text itself — see
    apps/api/services/job_match_service.py and docs/ARCHITECTURE.md's
    "Job Match Reconciliation" section).

    Insert-only, like `JobIntelligence`/`ResumeAIAnalysis`/
    `AtsAlignmentResult` (see docs/ARCHITECTURE.md's "Analysis/scoring
    versioning convention"), but as of AJI-014 keyed for idempotency
    exactly like `AtsAlignmentResult`: (user_id, job_id,
    resume_version_id, job_intelligence_id, engine_version). A cache hit
    on all five returns the existing row unchanged; a changed resume
    version, a new Job Intelligence snapshot, or a bumped
    `engine_version` always produces a new, additional row.

    Job Match answers a different question from `AtsAlignmentResult`
    ("how well does this exact resume demonstrate this exact JD's
    requirements?") — Job Match answers "how well does this job fit the
    user overall?" (skills/experience coverage, role/title alignment,
    location, and employment type). The two are never merged into one
    score or one table — see docs/ARCHITECTURE.md's "Job Match vs. ATS
    Alignment" section.
    """

    __tablename__ = "job_match_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # `ondelete="CASCADE"` on all three, matching every sibling analysis
    # table (`AtsAlignmentResult`, `GapAnalysis`, `JobEligibilityResult`,
    # `RequirementIntelligence`, `ResumeAIAnalysis`). Without it this was
    # the only such table whose rows blocked deleting the user, job or
    # resume version they were derived from: Postgres raised a
    # ForeignKeyViolation instead, so an account or a retired job could
    # not be removed once any Job Match had been calculated for it. A
    # derived, recomputable analysis row must never outlive - or pin -
    # the record it describes.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The exact Job Intelligence (AJI-012) snapshot this match's job-side
    # requirements were sourced from (AJI-014). Nullable because rows
    # persisted before AJI-014 predate this column and never had a Job
    # Intelligence snapshot behind them; those historical rows are never
    # backfilled or mutated. Every new row always sets this.
    job_intelligence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_intelligence.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Copied from JobIntelligence.content_fingerprint at match time, like
    # AtsAlignmentResult.job_content_fingerprint, so idempotency lookups
    # don't require a join.
    job_content_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    engine_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    confidence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class AtsAlignmentResult(Base):
    """A single ATS Alignment analysis (AJI-013): how well one exact
    `ResumeVersion` demonstrates the requirements of one exact
    `RequirementIntelligence` snapshot, for one user.

    Insert-only, like `JobMatchResult`/`JobIntelligence`/
    `ResumeAIAnalysis` (see docs/ARCHITECTURE.md's "Analysis/scoring
    versioning convention"): a new row is created whenever the resume
    version, the Requirement Intelligence snapshot, the Job Intelligence
    snapshot, or the ATS engine version changes, so a past analysis
    never silently mutates. ATS Alignment is a purely deterministic
    artifact (no AI call of its own — see services/ats_alignment/
    engine.py), so it follows the single `engine_version` convention
    rather than the analysis/analyzer/prompt/model split used by
    AI-derived artifacts.

    Unlike `JobIntelligence` (shared, job-scoped, no `user_id`), this
    table is personalized: the same job can be analyzed against
    different resumes/users, and a user must never be able to read
    another user's row (see docs/ARCHITECTURE.md's "Shared vs.
    personalized" section and AJI-013 section 14).

    AJI-020C (`requirement_intelligence_id`/
    `requirement_intelligence_fingerprint`, both nullable): ATS
    Alignment's requirement source is `RequirementIntelligence`
    (AJI-020A/B), not `JobIntelligence` — see
    apps/api/services/ats_alignment_service.py's
    `_build_job_requirements_from_requirement_intelligence`.
    `job_intelligence_id`/`job_content_fingerprint` are retained
    unchanged (still populated on every new row) purely for backward-
    compatible lineage/audit; they are no longer what drives the scored
    `result["requirement_results"]`. The two new columns are nullable
    because they were added via migration to an existing table — every
    row created going forward always populates both (see
    docs/ARCHITECTURE.md's AJI-020C section).
    """

    __tablename__ = "ats_alignment_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Copied from JobIntelligence.content_fingerprint at analysis time so
    # idempotency lookups don't require a join, and so this row's exact
    # JD-content identity stays legible even if read alongside history.
    job_content_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # AJI-020C: the actual requirement source (see the class docstring).
    # Nullable only because this was added via migration to an existing
    # table with existing rows — every row created by AJI-020C's
    # `calculate_ats_alignment` populates both.
    requirement_intelligence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirement_intelligence.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Copied from RequirementIntelligence.content_fingerprint at analysis
    # time, mirroring `job_content_fingerprint`'s same rationale.
    requirement_intelligence_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    engine_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    overall_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    confidence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Full requirement-level results: see
    # services/ats_alignment/contracts.py::RequirementAlignment for the
    # shape of each entry, plus must/preferred coverage counts and the
    # scoring formula version.
    result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class GapAnalysis(Base):
    """A single Gap Analysis & Job-Specific Suggestions result (AJI-015):
    for one exact `AtsAlignmentResult` (AJI-013, the canonical
    requirement-alignment source), a semantic explanation and a
    job-specific, evidence-constrained suggestion for every requirement
    that result classified as `partial` or `missing`.

    Gap Analysis never reimplements ATS scoring and never re-derives
    which requirements are gaps — every gap's status/jd_evidence/
    resume_evidence is copied verbatim from `ats_alignment_id`'s own
    `result["requirement_results"]` (see
    apps/api/services/gap_analysis/engine.py). It is an AI-derived
    artifact (deterministic gap selection feeds an evidence-constrained
    AI explanation/suggestion stage), so it follows the analysis/
    analyzer/prompt + model_provider/model_name convention, like
    `JobIntelligence` (see docs/ARCHITECTURE.md's "Analysis/scoring
    versioning convention").

    Insert-only, like every other AI/scoring artifact in this system: a
    new row is created whenever the resume version, the underlying ATS
    Alignment result, or the analyzer/prompt pipeline version changes.
    Historical rows are never overwritten or mutated.

    Personalized, like `AtsAlignmentResult` (unlike the shared,
    job-scoped `JobIntelligence`): the same job can be analyzed against
    different resumes/users, and a user must never be able to read
    another user's row.
    """

    __tablename__ = "gap_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The exact AJI-013 ATS Alignment result every gap in this row was
    # derived from. This is the concrete "tied to the specific Resume
    # Version and Job Intelligence snapshot" pin, and the primary
    # idempotency key alongside analyzer_version/prompt_version — since
    # AtsAlignmentResult is itself immutable and already pins
    # resume_version_id/job_intelligence_id/job_content_fingerprint.
    ats_alignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ats_alignment_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Copied from the AtsAlignmentResult at analysis time so idempotency
    # lookups and history don't require a join, mirroring
    # AtsAlignmentResult.job_content_fingerprint's own convention.
    job_content_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    analysis_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    analyzer_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # "complete" (no gaps to enrich, or the AI enrichment call succeeded)
    # or "partial" (there were gaps but the AI enrichment call itself
    # failed/was unavailable, so every gap fell back to a safe,
    # deterministic explanation/suggestion template). Never "failed" — a
    # failed result is not persisted at all; see
    # apps/api/services/gap_analysis/service.py.
    generation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="complete",
    )

    must_have_gap_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    preferred_gap_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Full gap-level results: see
    # apps/api/services/gap_analysis/contracts.py::GapAnalysisResult for
    # the exact shape.
    result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

class ResumeImprovement(Base):
    """One Resume Improvement Approval & Recheck record (AJI-021): the
    user's explicit approve/skip decisions over an exact `GapAnalysis`
    result, the child `ResumeVersion` those approvals produced, and the
    recheck of that child version against the same job.

    What this table is *not*: it is not a second Gap Analysis, not a
    second ATS scoring path, and not a resume editor. Every gap it
    references is read verbatim from `gap_analysis_id`'s stored result,
    and both the baseline and the recheck are ordinary
    `AtsAlignmentResult` rows produced by the existing, unmodified
    `calculate_ats_alignment()` (see docs/ARCHITECTURE.md's AJI-021
    section). No scoring formula is duplicated or changed here.

    Safety invariants this row is the audit trail for:

    - **Approval is mandatory.** A row only ever exists because the user
      explicitly approved at least one suggestion; nothing is applied
      automatically.
    - **`ADD_IF_TRUE` required explicit truth confirmation.** Every
      approved `ADD_IF_TRUE` decision in `result["decisions"]` carries
      `truth_confirmed = true`; the service rejects the request
      otherwise. `suggestion_type` is always read from the stored
      `GapAnalysis` row, never from the request body, so a client cannot
      relabel an `ADD_IF_TRUE` gap to dodge that check.
    - **Nothing is fabricated.** `applied_text` on every approved
      decision is the user's own text, verbatim. The system never
      contributes a qualification, an achievement, or an evidence claim
      of its own - see
      apps/api/services/resume_improvement/engine.py.
    - **The original is never overwritten.**
      `parent_resume_version_id` is left completely untouched;
      `child_resume_version_id` is a new, additional `ResumeVersion`
      whose `parent_version_id` points back at it.

    Uniqueness: `(user_id, gap_analysis_id, approval_fingerprint)` is
    unique, so re-submitting the same approval set for the same Gap
    Analysis returns the existing row instead of creating a second child
    version - enforced in the database, not only in application code, so
    two concurrent requests cannot both win.

    Mutability: unlike the purely insert-only analysis artifacts, the
    recheck fields (`recheck_status`, `recheck_error`,
    `recheck_ats_alignment_id`) are refreshed by a retry of a failed
    recheck. That transition is one-way: once
    `recheck_ats_alignment_id` is set it is never re-pointed, and the
    decisions, the fingerprint, and the child version are never
    mutated at all. A failed recheck therefore never costs the user the
    version they approved.
    """

    __tablename__ = "resume_improvements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The exact AJI-015 Gap Analysis result the user reviewed. Every
    # approved decision must reference a requirement_id present in this
    # row's stored gaps.
    gap_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gap_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The AJI-013 result the Gap Analysis itself was derived from - the
    # "before" side of the comparison, so Compare never needs to
    # recompute anything.
    baseline_ats_alignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ats_alignment_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    parent_resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    child_resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SHA-256 over the canonicalized approved decision set plus the
    # parent version and Gap Analysis identity - see
    # apps/api/services/resume_improvement/engine.py::
    # compute_approval_fingerprint.
    approval_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Resume Improvement is purely deterministic (it assembles text the
    # user wrote; it makes no AI call of its own), so it follows the
    # single `engine_version` convention - like `JobMatchResult` and
    # `AtsAlignmentResult`, not the analysis/analyzer/prompt split used
    # by AI-derived artifacts.
    engine_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    approved_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    skipped_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # "complete" (the recheck ran and produced an AtsAlignmentResult) or
    # "failed" (it did not). Never blocks or undoes the child version -
    # see the class docstring's mutability note.
    recheck_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="complete",
    )

    recheck_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recheck_ats_alignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ats_alignment_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The full decision record plus the before/after comparison: see
    # apps/api/services/resume_improvement/contracts.py::
    # ResumeImprovementResult for the exact shape.
    result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "gap_analysis_id",
            "approval_fingerprint",
            name="uq_resume_improvement_user_gap_fingerprint",
        ),
    )
