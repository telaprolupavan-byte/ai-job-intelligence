from __future__ import annotations

from services.job_matching.contracts import (
    EvidenceType,
    MatchStatus,
    ResumeEvidence,
    SkillEvidence,
)
from services.skills import normalize_skill


def build_resume_evidence_from_analysis(
    analysis,
    *,
    experience_years: float | None = None,
) -> ResumeEvidence:
    """
    Convert deterministic resume analysis into the evidence structure
    consumed by the Job Matching engine.
    """

    normalized_skills = [
        normalize_skill(skill)
        for skill in analysis.skills
    ]

    normalized_skills = list(
        dict.fromkeys(
            skill
            for skill in normalized_skills
            if skill
        )
    )

    evidence: list[SkillEvidence] = []

    for skill in normalized_skills:
        details = analysis.skill_evidence.get(
            skill,
            {},
        )

        demonstrated_mentions = details.get(
            "demonstrated_mentions",
            0,
        )

        skills_section_mentions = details.get(
            "skills_section_mentions",
            0,
        )

        if demonstrated_mentions > 0:
            # Used outside the skills section (work/project bullets):
            # treat as demonstrated professional experience.
            status = MatchStatus.MATCHED
            evidence_type = EvidenceType.EXPERIENCE
            evidence_text = (
                f"Resume demonstrates {skill} "
                "outside the skills section."
            )

        elif skills_section_mentions > 0:
            # Listed in the skills section only: a claim, not proof of use.
            status = MatchStatus.MATCHED
            evidence_type = EvidenceType.EXPLICIT
            evidence_text = (
                f"Resume explicitly lists {skill} "
                "in the skills section."
            )

        else:
            # No section or demonstrated mention was found for this skill;
            # do not claim a match on unsupported/weak evidence.
            status = MatchStatus.UNCERTAIN
            evidence_type = EvidenceType.INFERRED
            evidence_text = (
                f"Resume contains weak or unclear evidence "
                f"for {skill}."
            )

        evidence.append(
            SkillEvidence(
                skill=skill,
                status=status,
                evidence_type=evidence_type,
                evidence=evidence_text,
            )
        )

    return ResumeEvidence(
        skills=normalized_skills,
        experience_years=experience_years,
        evidence=evidence,
    )