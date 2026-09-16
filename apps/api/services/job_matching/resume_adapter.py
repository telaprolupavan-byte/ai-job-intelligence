from __future__ import annotations

from services.job_matching.contracts import (
    EvidenceType,
    MatchStatus,
    ResumeEvidence,
    SkillEvidence,
)
from services.job_matching.skill_normalizer import normalize_skill


def build_resume_evidence_from_analysis(
    analysis,
    *,
    experience_years: float | None = None,
) -> ResumeEvidence:
    """
    Convert the existing deterministic resume analysis into the
    evidence structure consumed by the job matching engine.
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
        skill_details = analysis.skill_evidence.get(
            skill,
            {},
        )

        demonstrated_mentions = skill_details.get(
            "demonstrated_mentions",
            0,
        )

        skills_section_mentions = skill_details.get(
            "skills_section_mentions",
            0,
        )

        if demonstrated_mentions > 0:
            evidence_type = EvidenceType.EXPERIENCE
            evidence_text = (
                f"Resume demonstrates {skill} outside the skills section."
            )
        elif skills_section_mentions > 0:
            evidence_type = EvidenceType.EXPLICIT
            evidence_text = (
                f"Resume explicitly lists {skill} in the skills section."
            )
        else:
            evidence_type = EvidenceType.INFERRED
            evidence_text = (
                f"Resume contains evidence associated with {skill}."
            )

        evidence.append(
            SkillEvidence(
                skill=skill,
                status=MatchStatus.MATCHED,
                evidence_type=evidence_type,
                evidence=evidence_text,
            )
        )

    return ResumeEvidence(
        skills=normalized_skills,
        experience_years=experience_years,
        evidence=evidence,
    )