"""Adapts an already-computed deterministic resume analysis into the
resume-side evidence profile consumed by services.ats_alignment.engine.

This module intentionally never calls `analyze_resume_deterministically`
itself and never touches the database or an AI provider — the caller
(apps/api/services/ats_alignment_service.py) computes the deterministic
analysis once and passes it in, exactly mirroring the existing
services.job_matching.resume_adapter convention (which does the same for
Job Match). This avoids a second, independent resume-parsing
implementation (AJI-013 section 20).

`analysis` is accepted structurally (duck-typed: any object exposing
`.skills` and `.skill_evidence`, as
`apps.api.services.resume_ai.deterministic.DeterministicResumeAnalysis`
does) rather than imported by type, so this module has zero import
dependency on apps.api.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.skills import normalize_skill


@dataclass
class ResumeEvidenceProfile:
    """Resume-side evidence available to the ATS Alignment engine.

    `raw_text` is kept (rather than only pre-extracted fields) because
    education and certification alignment are evaluated via grounded
    keyword search directly against it — every match is a literal
    substring of the resume, never an unverified AI claim (AJI-013
    section 7/8).
    """

    raw_text: str
    skills: list[str]
    skill_evidence: dict[str, dict]
    years_experience: float | None


def build_resume_evidence_profile(
    analysis: Any,
    *,
    raw_text: str,
    years_experience: float | None = None,
) -> ResumeEvidenceProfile:
    normalized_skills = [normalize_skill(skill) for skill in analysis.skills]

    normalized_skills = list(
        dict.fromkeys(skill for skill in normalized_skills if skill)
    )

    return ResumeEvidenceProfile(
        raw_text=raw_text,
        skills=normalized_skills,
        skill_evidence=analysis.skill_evidence,
        years_experience=years_experience,
    )
