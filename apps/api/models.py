import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
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

    storage_path: Mapped[str] = mapped_column(
        String(500),
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


class SavedJob(Base):
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
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


class JobMatchResult(Base):
    __tablename__ = "job_match_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id"),
        nullable=False,
        index=True,
    )

    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_versions.id"),
        nullable=False,
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