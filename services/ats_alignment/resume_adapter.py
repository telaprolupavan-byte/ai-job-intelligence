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
`.skills`, `.skill_evidence`, `.sections`, `.emails`, `.phones`,
`.bullets`, and `.structural_findings`, as
`apps.api.services.resume_ai.deterministic.DeterministicResumeAnalysis`
does) rather than imported by type, so this module has zero import
dependency on apps.api. The section/contact/bullet fields feed AJI-020's
Structure & Parseability score (see
services.ats_alignment.scoring.compute_structure_parseability) — they
were already computed by `analyze_resume_deterministically()` for
AJI-010 Resume Intelligence, so no second resume structure parser is
introduced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

    `detected_sections`/`has_contact_info`/`has_bullet_points`/
    `structural_finding_types` are presence-only signals (booleans/sets),
    never counts — this is what keeps the Structure & Parseability score
    (AJI-020) unaffected by resume length: a one-page and a three-page
    resume that both have an Experience section, contact info, and
    bullet-point formatting score identically on this dimension.
    """

    raw_text: str
    skills: list[str]
    skill_evidence: dict[str, dict]
    years_experience: float | None

    detected_sections: frozenset[str] = field(default_factory=frozenset)
    has_contact_info: bool = False
    has_bullet_points: bool = False
    structural_finding_types: frozenset[str] = field(default_factory=frozenset)


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

    detected_sections = frozenset(
        section.name for section in getattr(analysis, "sections", [])
    )

    has_contact_info = bool(getattr(analysis, "emails", None)) or bool(
        getattr(analysis, "phones", None)
    )

    has_bullet_points = bool(getattr(analysis, "bullets", None))

    structural_finding_types = frozenset(
        finding["type"]
        for finding in getattr(analysis, "structural_findings", [])
    )

    return ResumeEvidenceProfile(
        raw_text=raw_text,
        skills=normalized_skills,
        skill_evidence=analysis.skill_evidence,
        years_experience=years_experience,
        detected_sections=detected_sections,
        has_contact_info=has_contact_info,
        has_bullet_points=has_bullet_points,
        structural_finding_types=structural_finding_types,
    )
