from services.job_matching.contracts import (
    EvidenceType,
    JobRequirements,
    MatchStatus,
    ResumeEvidence,
    SkillEvidence,
)
from services.job_matching.skill_normalizer import normalize_skill


def match_skills(
    required_skills: list[str],
    resume_skills: list[str],
) -> list[SkillEvidence]:
    """
    Compare normalized job requirements against normalized resume skills.

    A skill is MATCHED only when the resume explicitly contains the
    normalized skill. Otherwise it is MISSING.

    This function does not infer experience or qualifications.
    """

    normalized_resume_skills = {
        normalize_skill(skill)
        for skill in resume_skills
        if normalize_skill(skill)
    }

    results: list[SkillEvidence] = []

    for skill in required_skills:
        normalized_skill = normalize_skill(skill)

        if not normalized_skill:
            continue

        if normalized_skill in normalized_resume_skills:
            results.append(
                SkillEvidence(
                    skill=normalized_skill,
                    status=MatchStatus.MATCHED,
                    evidence_type=EvidenceType.EXPLICIT,
                    evidence=f"Resume explicitly lists {normalized_skill}.",
                )
            )
        else:
            results.append(
                SkillEvidence(
                    skill=normalized_skill,
                    status=MatchStatus.MISSING,
                    evidence_type=EvidenceType.NONE,
                    evidence=None,
                )
            )

    return results


def match_job_requirements(
    requirements: JobRequirements,
    resume_skills: list[str],
) -> tuple[list[SkillEvidence], list[SkillEvidence]]:
    """
    Match must-have and preferred job skills separately.
    """

    must_have_results = match_skills(
        requirements.must_have_skills,
        resume_skills,
    )

    preferred_results = match_skills(
        requirements.preferred_skills,
        resume_skills,
    )

    return must_have_results, preferred_results


def match_skills_with_evidence(
    required_skills: list[str],
    resume_evidence: ResumeEvidence,
) -> list[SkillEvidence]:
    """
    Compare required skills against resume evidence, preserving each
    skill's actual evidence type/status (e.g. Skills-section-only vs.
    demonstrated experience) instead of collapsing every match to a
    single generic "explicit" evidence type.
    """

    evidence_by_skill = {
        item.skill: item
        for item in resume_evidence.evidence
    }

    results: list[SkillEvidence] = []

    for skill in required_skills:
        normalized_skill = normalize_skill(skill)

        if not normalized_skill:
            continue

        existing_evidence = evidence_by_skill.get(normalized_skill)

        if existing_evidence is not None:
            results.append(existing_evidence)
        else:
            results.append(
                SkillEvidence(
                    skill=normalized_skill,
                    status=MatchStatus.MISSING,
                    evidence_type=EvidenceType.NONE,
                    evidence=None,
                )
            )

    return results


def match_job_requirements_with_evidence(
    requirements: JobRequirements,
    resume_evidence: ResumeEvidence,
) -> tuple[list[SkillEvidence], list[SkillEvidence]]:
    """
    Match must-have and preferred job skills using the resume's actual
    per-skill evidence rather than a flat skill-name presence check.
    """

    must_have_results = match_skills_with_evidence(
        requirements.must_have_skills,
        resume_evidence,
    )

    preferred_results = match_skills_with_evidence(
        requirements.preferred_skills,
        resume_evidence,
    )

    return must_have_results, preferred_results