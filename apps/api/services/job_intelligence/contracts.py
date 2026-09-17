"""The Job Intelligence contract (AJI-012).

This is the canonical structured representation of "what does this
specific job require?" — the output later consumed by AJI-013 (ATS
Alignment), AJI-014 (Gap Analysis), AJI-015 (Suggestions), and AJI-016
(Priority Ranking). It intentionally contains no score, no ranking, and
no user-specific data: see docs/ARCHITECTURE.md for the shared-vs-
personalized boundary.

Confidence reuses the existing high/medium/low convention from
`apps.api.services.resume_ai.contracts` rather than introducing a new
numeric-confidence representation.

Fields are deliberately optional/`"unknown"` by default: absence of
observable evidence must remain absence, never a guessed value.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Level = Literal["required", "preferred"]
Confidence = Literal["high", "medium", "low"]

EmploymentType = Literal[
    "full_time",
    "part_time",
    "contract",
    "contract_to_hire",
    "temporary",
    "internship",
    "other",
    "unknown",
]

RemoteType = Literal["remote", "hybrid", "onsite", "unknown"]

SponsorshipStatus = Literal["required", "unavailable", "available", "unknown"]
CitizenshipStatus = Literal["required", "preferred", "unknown"]
ClearanceStatus = Literal["required", "preferred", "unknown"]
WorkAuthorizationStatus = Literal[
    "explicit_requirement", "explicit_restriction", "unknown"
]
CompensationPeriod = Literal["annual", "hourly", "unknown"]


class SkillRequirement(BaseModel):
    canonical_skill: str = Field(min_length=1)
    level: Level
    evidence_text: str = Field(min_length=1)
    confidence: Confidence = "high"


class ExperienceRequirement(BaseModel):
    level: Level
    minimum_years: float | None = None
    maximum_years: float | None = None
    area: str | None = None
    context: str | None = None
    evidence_text: str = Field(min_length=1)
    confidence: Confidence = "high"


class EducationRequirement(BaseModel):
    level: Level
    degree_level: str | None = None
    field_of_study: str | None = None
    evidence_text: str = Field(min_length=1)
    confidence: Confidence = "high"


class CertificationRequirement(BaseModel):
    level: Level
    name: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    confidence: Confidence = "high"


class ResponsibilityItem(BaseModel):
    description: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class JobIdentity(BaseModel):
    original_title: str = Field(min_length=1)
    normalized_title: str | None = None
    normalized_title_confidence: Confidence | None = None
    role_family: str | None = None
    role_family_confidence: Confidence | None = None
    seniority: str | None = None
    seniority_confidence: Confidence | None = None


class EmploymentInfo(BaseModel):
    employment_type: EmploymentType = "unknown"
    evidence_text: str | None = None


class LocationInfo(BaseModel):
    raw_location: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    additional_locations: list[str] = Field(default_factory=list)
    remote_type: RemoteType = "unknown"
    work_arrangement_text: str | None = None
    relocation_mentioned: bool = False
    relocation_evidence: str | None = None


class AuthorizationSignals(BaseModel):
    sponsorship: SponsorshipStatus = "unknown"
    citizenship: CitizenshipStatus = "unknown"
    clearance: ClearanceStatus = "unknown"
    work_authorization: WorkAuthorizationStatus = "unknown"
    evidence: list[str] = Field(default_factory=list)


class CompensationInfo(BaseModel):
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    period: CompensationPeriod = "unknown"
    evidence_text: str | None = None


class DomainInfo(BaseModel):
    value: str | None = None
    confidence: Confidence | None = None
    evidence_text: str | None = None


class JobIntelligenceResult(BaseModel):
    """The full, versioned Job Intelligence contract for one JD snapshot."""

    analysis_version: str
    job_id: str

    identity: JobIdentity
    employment: EmploymentInfo
    location: LocationInfo

    required_skills: list[SkillRequirement] = Field(default_factory=list)
    preferred_skills: list[SkillRequirement] = Field(default_factory=list)

    required_experience: list[ExperienceRequirement] = Field(
        default_factory=list
    )
    preferred_experience: list[ExperienceRequirement] = Field(
        default_factory=list
    )

    education: list[EducationRequirement] = Field(default_factory=list)
    certifications: list[CertificationRequirement] = Field(
        default_factory=list
    )
    responsibilities: list[ResponsibilityItem] = Field(default_factory=list)

    authorization: AuthorizationSignals = Field(
        default_factory=AuthorizationSignals
    )
    compensation: CompensationInfo = Field(default_factory=CompensationInfo)
    domain: DomainInfo = Field(default_factory=DomainInfo)
