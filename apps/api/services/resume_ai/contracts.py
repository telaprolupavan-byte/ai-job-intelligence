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


class ResumePositioning(BaseModel):
    apparent_target_role: str | None = None
    apparent_specialization: str | None = None
    apparent_seniority: str | None = None
    positioning_strengths: list[str] = Field(default_factory=list)
    positioning_risks: list[str] = Field(default_factory=list)


class ResumeSummary(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    top_priorities: list[str] = Field(default_factory=list)


class ResumeAIResult(BaseModel):
    analysis_version: str
    resume_version_id: str
    profile: dict
    positioning: ResumePositioning
    sections: dict
    skills: dict
    experience: dict
    technical_depth: dict
    structure: dict
    findings: list[ResumeFinding]
    summary: ResumeSummary