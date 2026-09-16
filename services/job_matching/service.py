from services.job_matching.contracts import (
    JobMatchResult,
    JobRequirements,
    ResumeEvidence,
)
from services.job_matching.evidence import build_resume_evidence
from services.job_matching.matcher import (
    match_job_requirements,
    match_job_requirements_with_evidence,
)
from services.job_matching.scorer import (
    build_match_result,
    calculate_match_confidence,
    score_employment_type,
    score_experience,
    score_location,
    score_role_alignment,
)


class JobMatchingService:
    """
    Application-level service for calculating a deterministic
    job match between a resume and a job.

    This service does not access the database directly.

    Database/API integration belongs to Checkpoint 11.
    """

    def calculate_match(
        self,
        *,
        job_title: str,
        job_requirements: JobRequirements,
        resume_skills: list[str] | None = None,
        resume_evidence: ResumeEvidence | None = None,
        resume_years: float | None = None,
        resume_titles: list[str] | None = None,
        job_remote_type: str | None = None,
        job_location: str | None = None,
        job_employment_type: str | None = None,
        preferred_remote_type: str | None = None,
        preferred_location: str | None = None,
        preferred_employment_type: str | None = None,
    ) -> JobMatchResult:
        """
        Calculate a complete deterministic Job Match result.

        When ``resume_evidence`` (as produced by
        build_resume_evidence_from_analysis) is supplied, its per-skill
        evidence type/status is preserved so Skills-section-only
        mentions are not reported as demonstrated experience. When only
        a flat ``resume_skills`` list is supplied, matching falls back
        to the simpler presence-based evidence used previously.
        """

        if resume_evidence is None:
            resume_evidence = build_resume_evidence(
                skills=resume_skills or [],
                experience_years=resume_years,
            )

            must_have_matches, preferred_matches = (
                match_job_requirements(
                    requirements=job_requirements,
                    resume_skills=resume_evidence.skills,
                )
            )
        else:
            must_have_matches, preferred_matches = (
                match_job_requirements_with_evidence(
                    requirements=job_requirements,
                    resume_evidence=resume_evidence,
                )
            )

        experience_score = score_experience(
            resume_years=resume_evidence.experience_years,
            requirements=(
                job_requirements.must_have_experience
                + job_requirements.preferred_experience
            ),
            max_score=20,
        )

        role_score = score_role_alignment(
            job_title=job_title,
            resume_titles=resume_titles or [],
            max_score=15,
        )

        location_score = score_location(
            job_remote_type=job_remote_type,
            job_location=job_location,
            preferred_remote_type=preferred_remote_type,
            preferred_location=preferred_location,
            max_score=10,
        )

        employment_score = score_employment_type(
            job_employment_type=job_employment_type,
            preferred_employment_type=preferred_employment_type,
            max_score=5,
        )

        confidence = calculate_match_confidence(
            has_job_requirements=bool(
                job_requirements.must_have_skills
                or job_requirements.preferred_skills
                or job_requirements.must_have_experience
                or job_requirements.preferred_experience
            ),
            has_resume_skills=bool(resume_evidence.skills),
            has_experience_data=(
                resume_evidence.experience_years is not None
            ),
            has_role_data=bool(resume_titles),
        )

        return build_match_result(
            must_have_matches=must_have_matches,
            preferred_matches=preferred_matches,
            experience_score=experience_score,
            role_score=role_score,
            location_score=location_score,
            employment_score=employment_score,
            confidence=confidence,
        )