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


class PreferenceResponse(BaseModel):
    id: str
    user_id: str
    employment_types: list[str] | None
    locations: list[str] | None
    remote_preference: str | None
    target_titles: list[str] | None


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