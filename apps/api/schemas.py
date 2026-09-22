from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# =========================
# Authentication
# =========================

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


# =========================
# Profile
# =========================

class ProfileUpdate(BaseModel):
    full_name: str | None = Field(
        default=None,
        max_length=255,
    )
    phone: str | None = Field(
        default=None,
        max_length=50,
    )
    location: str | None = Field(
        default=None,
        max_length=255,
    )
    summary: str | None = None
    years_experience: float | None = Field(
        default=None,
        ge=0,
    )
    target_titles: list[str] | None = None


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: str | None
    phone: str | None
    location: str | None
    summary: str | None
    years_experience: float | None
    target_titles: list[str] | None


# =========================
# Preferences
# =========================

class PreferenceUpdate(BaseModel):
    employment_types: list[str] | None = None
    locations: list[str] | None = None
    remote_preference: str | None = Field(
        default=None,
        max_length=50,
    )
    target_titles: list[str] | None = None

    # Hard eligibility fields (AJI-011). See PreferenceResponse and
    # docs/ARCHITECTURE.md for what each one means.
    excluded_locations: list[str] | None = None
    requires_sponsorship: bool | None = None
    is_us_citizen: bool | None = None
    has_security_clearance: bool | None = None
    enforce_minimum_experience: bool | None = None


class PreferenceResponse(BaseModel):
    id: str
    user_id: str
    employment_types: list[str] | None
    locations: list[str] | None
    remote_preference: str | None
    target_titles: list[str] | None

    # Hard eligibility fields (AJI-011).
    #
    # `employment_types`/`locations`/`remote_preference` above double as
    # hard-eligibility "accepted" values when non-empty; these fields
    # cover what those can't express: explicit exclusions and work
    # authorization. None means "unspecified" (no hard restriction).
    excluded_locations: list[str] | None
    requires_sponsorship: bool | None
    is_us_citizen: bool | None
    has_security_clearance: bool | None
    enforce_minimum_experience: bool


# =========================
# Resumes
# =========================

class ResumeResponse(BaseModel):
    id: str
    filename: str
    created_at: str
    has_text: bool
    version_count: int
    master_version_id: str | None
    master_version_name: str | None
    master_version_created_at: str | None


class ResumeDetailResponse(BaseModel):
    id: str
    filename: str
    original_text: str | None
    created_at: str


class ResumeVersionResponse(BaseModel):
    id: str
    resume_id: str
    name: str
    original_filename: str
    content_text: str
    is_master: bool
    has_analysis: bool
    created_at: str

    # AJI-021 lineage. `parent_version_id` is None for every uploaded
    # version; `source` is "upload" or "improvement"; `has_file` is False
    # for a version generated from approved improvements, which has no
    # uploaded document to download.
    parent_version_id: str | None = None
    source: str = "upload"
    has_file: bool = True


class ResumeUploadResponse(BaseModel):
    id: str
    version_id: str
    filename: str
    version_name: str
    created_at: str
    valid: bool
    word_count: int
    character_count: int
    section_matches: list[str]
    warnings: list[str]
    is_new_resume: bool
    duplicate: bool

# =========================
# Application Tracking
# =========================

APPLICATION_STATUSES = [
    "saved",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "withdrawn",
]

ApplicationStatus = Literal[
    "saved",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "withdrawn",
]


class CreateApplicationRequest(BaseModel):
    job_id: str


class UpdateApplicationStatusRequest(BaseModel):
    status: ApplicationStatus


class ApplicationJobSummary(BaseModel):
    id: str
    title: str
    company: str | None
    location: str | None
    employment_type: str | None
    remote_type: str | None
    application_url: str | None


class ApplicationStatusEventResponse(BaseModel):
    status: str
    created_at: str


class ApplicationResponse(BaseModel):
    id: str
    job: ApplicationJobSummary
    status: str
    applied_at: str | None
    created_at: str
    updated_at: str


class ApplicationDetailResponse(ApplicationResponse):
    status_history: list[ApplicationStatusEventResponse]


# =========================
# Job Submission (AJI-022)
# =========================

# Generous for a real posting (the longest real JDs are ~15-20k chars),
# while bounding what one request can push through two AI pipelines.
JOB_SUBMISSION_MAX_CONTENT_LENGTH = 50_000


class JobSubmissionRequest(BaseModel):
    """Pasted job content. Validated here only for shape/size - the text
    itself is untrusted data, never interpreted as instructions."""

    content: str = Field(
        min_length=1,
        max_length=JOB_SUBMISSION_MAX_CONTENT_LENGTH,
    )
    title: str | None = Field(default=None, max_length=500)
    company: str | None = Field(default=None, max_length=255)
