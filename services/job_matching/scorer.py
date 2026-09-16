from services.job_matching.contracts import (
    ExperienceRequirement,
    JobMatchResult,
    MatchComponent,
    MatchStatus,
    SkillEvidence,
)
from services.job_matching.skill_normalizer import normalize_skill


# ---------------------------------------------------------------------------
# Requirement scoring
# ---------------------------------------------------------------------------


def score_requirement_matches(
    matches: list[SkillEvidence],
    max_score: float,
) -> float:
    """
    Score a requirement group proportionally.

    MATCHED requirements receive credit.
    MISSING and UNCERTAIN requirements receive no credit.
    """

    if not matches:
        return max_score

    matched_count = sum(
        1
        for match in matches
        if match.status == MatchStatus.MATCHED
    )

    score = (matched_count / len(matches)) * max_score

    return round(score, 2)


def score_must_have_requirements(
    matches: list[SkillEvidence],
) -> float:
    """Score must-have requirements out of 35 points."""

    return score_requirement_matches(
        matches=matches,
        max_score=35,
    )


def score_preferred_requirements(
    matches: list[SkillEvidence],
) -> float:
    """Score preferred requirements out of 15 points."""

    return score_requirement_matches(
        matches=matches,
        max_score=15,
    )


# ---------------------------------------------------------------------------
# Experience scoring
# ---------------------------------------------------------------------------


def score_experience(
    resume_years: float | None,
    requirements: list[ExperienceRequirement],
    max_score: float = 20,
) -> float:
    """
    Score resume experience against explicit minimum experience
    requirements.

    Unknown experience receives no credit.

    If multiple minimum requirements exist, the highest explicit
    minimum is used as the threshold.
    """

    if not requirements:
        return max_score

    if resume_years is None:
        return 0

    minimum_years = max(
        (
            requirement.minimum_years
            for requirement in requirements
            if requirement.minimum_years is not None
        ),
        default=None,
    )

    if minimum_years is None or minimum_years <= 0:
        return max_score

    score = min(
        resume_years / minimum_years,
        1.0,
    ) * max_score

    return round(score, 2)


# ---------------------------------------------------------------------------
# Role alignment scoring
# ---------------------------------------------------------------------------


def score_role_alignment(
    job_title: str,
    resume_titles: list[str],
    max_score: float = 15,
) -> float:
    """
    Score broad role/title alignment.

    Exact normalized title match receives full credit.

    A meaningful shared term receives partial credit.

    Unrelated titles receive zero.

    This is intentionally deterministic and conservative.
    """

    if not job_title or not resume_titles:
        return 0

    normalized_job_title = normalize_skill(job_title)

    job_words = {
        word
        for word in normalized_job_title.split()
        if len(word) > 2
    }

    if not job_words:
        return 0

    best_score = 0.0

    for title in resume_titles:
        normalized_title = normalize_skill(title)

        if not normalized_title:
            continue

        # Exact title match.
        if normalized_title == normalized_job_title:
            return max_score

        title_words = {
            word
            for word in normalized_title.split()
            if len(word) > 2
        }

        overlap = job_words & title_words

        if overlap:
            partial_score = (
                len(overlap) / len(job_words)
            ) * max_score * 0.75

            best_score = max(
                best_score,
                round(partial_score, 2),
            )

    return round(best_score, 2)


# ---------------------------------------------------------------------------
# Location scoring
# ---------------------------------------------------------------------------


def score_location(
    *,
    job_remote_type: str | None,
    job_location: str | None,
    preferred_remote_type: str | None = None,
    preferred_location: str | None = None,
    max_score: float = 10,
) -> float:
    """
    Score compatibility between a job and user location preferences.

    Rules:

    - No user location preference → full credit.
    - Remote job with remote preference → full credit.
    - Matching remote type → full credit.
    - Explicit matching location → full credit.
    - Explicit mismatch → zero.
    - Unknown information → partial credit rather than inventing a match.
    """

    if not preferred_remote_type and not preferred_location:
        return max_score

    remote_type = (
        job_remote_type.strip().lower()
        if job_remote_type
        else None
    )

    preferred_remote = (
        preferred_remote_type.strip().lower()
        if preferred_remote_type
        else None
    )

    job_loc = (
        job_location.strip().lower()
        if job_location
        else None
    )

    preferred_loc = (
        preferred_location.strip().lower()
        if preferred_location
        else None
    )

    # Explicit remote preference.
    if preferred_remote:
        if remote_type == preferred_remote:
            return max_score

        if remote_type is None:
            return round(max_score * 0.5, 2)

        # A remote preference does not automatically mean that
        # hybrid/onsite is acceptable.
        if remote_type != preferred_remote:
            return 0

    # Explicit location preference.
    if preferred_loc:
        if not job_loc:
            return round(max_score * 0.5, 2)

        if preferred_loc in job_loc or job_loc in preferred_loc:
            return max_score

        return 0

    return max_score


# ---------------------------------------------------------------------------
# Employment type scoring
# ---------------------------------------------------------------------------


def score_employment_type(
    *,
    job_employment_type: str | None,
    preferred_employment_type: str | None = None,
    max_score: float = 5,
) -> float:
    """
    Score compatibility between job employment type and preference.

    Unknown job employment type receives partial credit.
    Explicit mismatch receives zero.
    """

    if not preferred_employment_type:
        return max_score

    if not job_employment_type:
        return round(max_score * 0.5, 2)

    job_type = job_employment_type.strip().lower()
    preferred_type = preferred_employment_type.strip().lower()

    if job_type == preferred_type:
        return max_score

    return 0


# ---------------------------------------------------------------------------
# Overall match result
# ---------------------------------------------------------------------------


def build_match_result(
    must_have_matches: list[SkillEvidence],
    preferred_matches: list[SkillEvidence],
    experience_score: float,
    role_score: float,
    location_score: float,
    employment_score: float,
    confidence: str = "deterministic",
) -> JobMatchResult:
    """
    Build the complete deterministic Job Match result.

    The final score is the sum of independently calculated,
    explainable components.
    """

    must_have_score = score_must_have_requirements(
        must_have_matches
    )

    preferred_score = score_preferred_requirements(
        preferred_matches
    )

    components = [
        MatchComponent(
            name="must_have_requirements",
            score=must_have_score,
            max_score=35,
            explanation=(
                "Measures satisfaction of required job skills."
            ),
        ),
        MatchComponent(
            name="preferred_requirements",
            score=preferred_score,
            max_score=15,
            explanation=(
                "Measures satisfaction of preferred job skills."
            ),
        ),
        MatchComponent(
            name="experience",
            score=experience_score,
            max_score=20,
            explanation=(
                "Measures experience against explicit requirements."
            ),
        ),
        MatchComponent(
            name="role_alignment",
            score=role_score,
            max_score=15,
            explanation=(
                "Measures alignment between target role and resume roles."
            ),
        ),
        MatchComponent(
            name="location",
            score=location_score,
            max_score=10,
            explanation=(
                "Measures compatibility with the job location."
            ),
        ),
        MatchComponent(
            name="employment_type",
            score=employment_score,
            max_score=5,
            explanation=(
                "Measures compatibility with employment preferences."
            ),
        ),
    ]

    total_score = round(
        sum(component.score for component in components),
        2,
    )

    matched_must_have = [
        match
        for match in must_have_matches
        if match.status == MatchStatus.MATCHED
    ]

    missing_must_have = [
        match
        for match in must_have_matches
        if match.status == MatchStatus.MISSING
    ]

    matched_preferred = [
        match
        for match in preferred_matches
        if match.status == MatchStatus.MATCHED
    ]

    missing_preferred = [
        match
        for match in preferred_matches
        if match.status == MatchStatus.MISSING
    ]

    strengths = [
        f"Matches required skill: {match.skill}"
        for match in matched_must_have
    ]

    skill_gaps = [
        match.skill
        for match in missing_must_have
    ]

    return JobMatchResult(
        score=total_score,
        confidence=confidence,
        must_have_matches=matched_must_have,
        must_have_gaps=missing_must_have,
        preferred_matches=matched_preferred,
        preferred_gaps=missing_preferred,
        components=components,
        strengths=strengths,
        skill_gaps=skill_gaps,
    )


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def calculate_match_confidence(
    *,
    has_job_requirements: bool,
    has_resume_skills: bool,
    has_experience_data: bool,
    has_role_data: bool,
) -> str:
    """
    Estimate confidence based on available structured evidence.

    This represents confidence in the calculation, NOT the probability
    of receiving an interview or job offer.
    """

    available = sum(
        [
            has_job_requirements,
            has_resume_skills,
            has_experience_data,
            has_role_data,
        ]
    )

    if available >= 4:
        return "high"

    if available >= 2:
        return "medium"

    return "low"