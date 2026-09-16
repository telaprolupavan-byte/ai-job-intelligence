import re

from services.job_matching.contracts import (
    ExperienceRequirement,
    JobRequirements,
)
from services.job_matching.skill_normalizer import (
    SKILL_ALIASES,
    normalize_skill,
)

# Surface forms too short/ambiguous to safely search for in free-form prose
# (still valid for normalize_skill() when a skill is already explicitly given).
_EXTRACTION_EXCLUDED_SURFACE_FORMS = {"ai", "ml", "js", "ts", "py"}

_SKILL_SEARCH_TERMS = sorted(
    (
        surface_form
        for surface_form in SKILL_ALIASES
        if surface_form not in _EXTRACTION_EXCLUDED_SURFACE_FORMS
    ),
    key=len,
    reverse=True,
)

PREFERRED_SECTION_MARKERS = (
    "nice to have",
    "nice-to-have",
    "preferred qualifications",
    "preferred skills",
    "preferred experience",
    "bonus points",
)


def extract_job_skills(text: str) -> list[str]:
    """
    Find individual technical skills explicitly present in job text.

    Only matches against a known skill vocabulary (whole-word/phrase),
    normalized through the existing skill normalizer. This does not treat
    arbitrary words as skills and does not infer skills that are absent.
    """
    if not text:
        return []

    normalized_text = f" {re.sub(r'\s+', ' ', text).strip().lower()} "

    found: list[str] = []
    seen: set[str] = set()

    for surface_form in _SKILL_SEARCH_TERMS:
        pattern = re.compile(
            rf"(?<![a-z0-9]){re.escape(surface_form)}(?![a-z0-9])"
        )

        if not pattern.search(normalized_text):
            continue

        canonical = normalize_skill(surface_form)

        if canonical and canonical not in seen:
            found.append(canonical)
            seen.add(canonical)

    return found


def split_preferred_section(text: str) -> tuple[str, str]:
    """
    Split job text into (must_have_text, preferred_text) using common
    "nice to have"/"preferred" section markers. When no such marker is
    present, the entire text is treated as must-have rather than guessing.
    """
    if not text:
        return "", ""

    lowered = text.lower()
    earliest_index: int | None = None

    for marker in PREFERRED_SECTION_MARKERS:
        index = lowered.find(marker)

        if index != -1 and (earliest_index is None or index < earliest_index):
            earliest_index = index

    if earliest_index is None:
        return text, ""

    return text[:earliest_index], text[earliest_index:]


def extract_experience_requirements(
    text: str,
) -> list[ExperienceRequirement]:
    """
    Extract simple years-of-experience requirements.

    Examples:
        "3+ years of experience"
        "5 years experience"
        "2 years of experience"

    This intentionally handles only explicit patterns.
    Ambiguous language is not guessed.
    """
    if not text:
        return []

    pattern = re.compile(
        r"(?P<years>\d+(?:\.\d+)?)\+?\s+years?"
        r"(?:\s+of)?\s+experience",
        re.IGNORECASE,
    )

    requirements: list[ExperienceRequirement] = []

    for match in pattern.finditer(text):
        years = float(match.group("years"))

        requirements.append(
            ExperienceRequirement(
                minimum_years=years,
                description=match.group(0),
            )
        )

    return requirements


def build_job_requirements(
    must_have_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
    must_have_text: str = "",
    preferred_text: str = "",
) -> JobRequirements:
    """
    Build normalized structured job requirements.

    Explicitly provided skill lists are combined with individual skills
    detected in the requirement text (matched against a known skill
    vocabulary, not inferred from arbitrary words). Experience
    requirements are extracted from the must-have/preferred text.
    """
    normalized_must_have = [
        normalize_skill(skill)
        for skill in (must_have_skills or [])
    ] + extract_job_skills(must_have_text)

    normalized_preferred = [
        normalize_skill(skill)
        for skill in (preferred_skills or [])
    ] + extract_job_skills(preferred_text)

    normalized_must_have = list(
        dict.fromkeys(
            skill for skill in normalized_must_have if skill
        )
    )

    normalized_preferred = list(
        dict.fromkeys(
            skill for skill in normalized_preferred if skill
        )
    )

    # A skill already required as must-have is not also listed as preferred.
    normalized_preferred = [
        skill
        for skill in normalized_preferred
        if skill not in normalized_must_have
    ]

    return JobRequirements(
        must_have_skills=normalized_must_have,
        preferred_skills=normalized_preferred,
        must_have_experience=extract_experience_requirements(
            must_have_text
        ),
        preferred_experience=extract_experience_requirements(
            preferred_text
        ),
    )