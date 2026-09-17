from services.job_matching.contracts import (
    EvidenceType,
    MatchStatus,
    ResumeEvidence,
    SkillEvidence,
)
from services.skills import normalize_skill

def build_resume_evidence(
    skills: list[str] | None = None,
    experience_years: float | None = None,
) -> ResumeEvidence:
    """
    Build normalized resume evidence from already-extracted
    resume information.

    This function intentionally does not infer professional
    experience from skill names alone.
    """

    normalized_skills = [
        normalize_skill(skill)
        for skill in (skills or [])
    ]

    normalized_skills = list(
        dict.fromkeys(
            skill for skill in normalized_skills if skill
        )
    )

    evidence = [
        SkillEvidence(
            skill=skill,
            status=MatchStatus.MATCHED,
            evidence_type=EvidenceType.EXPLICIT,
            evidence=f"Resume explicitly lists {skill}.",
        )
        for skill in normalized_skills
    ]

    return ResumeEvidence(
        skills=normalized_skills,
        experience_years=experience_years,
        evidence=evidence,
    )