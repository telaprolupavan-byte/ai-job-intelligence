from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Priority = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]


class ResumeFinding(BaseModel):
    category: str = Field(min_length=1)
    priority: Priority
    finding: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    confidence: Confidence


class ResumeReview(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    findings: list[ResumeFinding] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class SkillEvidence(BaseModel):
    skill: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    demonstrated: bool


class WorkHistoryEntry(BaseModel):
    company: str | None = None
    title: str | None = None
    duration: str | None = None
    summary: str | None = None


class EducationEntry(BaseModel):
    institution: str | None = None
    credential: str | None = None
    field_of_study: str | None = None
    graduation: str | None = None


class ProjectEntry(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    technologies: list[str] = Field(default_factory=list)


class ResumeDecoding(BaseModel):
    professional_profile: str | None = None
    technical_profile: str | None = None
    work_history: list[WorkHistoryEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[SkillEvidence] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class RoleMatch(BaseModel):
    role: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class PositionIdentification(BaseModel):
    primary_roles: list[RoleMatch] = Field(default_factory=list)
    secondary_roles: list[RoleMatch] = Field(default_factory=list)
    adjacent_roles: list[RoleMatch] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)


class ResumeAIResult(BaseModel):
    """The result of the single comprehensive resume AI analysis.

    Structured as RESUME INTELLIGENCE: a Resume Review (feedback on the
    resume as written), a Resume Decoding (what the resume says about the
    candidate), and a Position Identification (which roles the resume's
    evidence supports).
    """

    analysis_version: str
    resume_version_id: str
    review: ResumeReview
    decoding: ResumeDecoding
    position_identification: PositionIdentification
