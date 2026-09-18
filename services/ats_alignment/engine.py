"""ATS Alignment pure engine (AJI-013).

Answers: "how well does this exact ResumeVersion demonstrate this exact
JD's requirements?" — given already-extracted job requirements
(`JobRequirementItem`, adapted from an AJI-012 `JobIntelligence`
snapshot) and an already-computed resume evidence profile
(`ResumeEvidenceProfile`, adapted from the existing deterministic resume
analyzer). No database access, no AI call, no re-parsing of raw JD text
or a second resume parser — see module docstrings on
services.ats_alignment.resume_adapter and
apps/api/services/ats_alignment_service.py for why those inputs are
built the way they are.

AI usage (AJI-013 section 8): this engine is entirely deterministic.
Semantic-equivalence handling (e.g. "GCP" == "Google Cloud Platform")
already happens upstream, once, in the shared canonical skill vocabulary
(services.skills) that both Job Intelligence and Resume Intelligence
extraction already go through — so exact-vs-synonym skill matching does
not need its own AI call here. Education/certification matching is a
grounded keyword search directly against the resume's raw text: every
`resume_evidence` string returned below is a literal substring of the
resume, so nothing here can assert an unsupported resume fact. A future
ticket may layer an AI semantic-interpretation stage on top of this
engine for genuinely ambiguous cases (the spec allows, but does not
require, that) — this is a deliberate, minimal v1 scope decision, not an
oversight.

Evidence rules (AJI-013 section 7):
- `matched` is only used when the resume evidence is a direct or
  quantitatively-verified match (skill demonstrated outside a skills
  list, sufficient declared years, degree at/above the required rank,
  the certification's own significant terms all present in the resume).
- `partial` is used when there is *some* related evidence but the
  requirement is not fully demonstrated (skill listed only in a skills
  section with no demonstrated use, declared years below the minimum,
  a lower degree than required, or an education requirement whose
  degree level is satisfied but field of study is not confirmed).
- `missing` is used only when no such evidence exists in the resume.
"""

from __future__ import annotations

import re

from services.ats_alignment.contracts import (
    AtsAlignmentResult,
    Confidence,
    JobRequirementItem,
    RequirementAlignment,
    RequirementRelationshipGroup,
    ScreeningConstraintInfo,
)
from services.ats_alignment.resume_adapter import ResumeEvidenceProfile
from services.ats_alignment.scoring import (
    SCORING_VERSION,
    compute_overall_confidence,
    compute_overall_score,
)


ENGINE_VERSION = "1.0.0"


def _carry_requirement_metadata(requirement: JobRequirementItem) -> dict:
    """AJI-020A metadata (AJI-020C) carried onto every `RequirementAlignment`
    unchanged — never read by any evaluator's status/confidence logic
    below, and never read by `services.ats_alignment.scoring`."""
    return {
        "hard_requirement": requirement.hard_requirement,
        "ambiguous": requirement.ambiguous,
        "ambiguity_reason": requirement.ambiguity_reason,
    }


# ---------------------------------------------------------------------------
# Skill alignment
# ---------------------------------------------------------------------------

def _evaluate_skill(
    requirement: JobRequirementItem,
    resume: ResumeEvidenceProfile,
) -> RequirementAlignment:
    skill = requirement.canonical_skill or ""
    details = resume.skill_evidence.get(skill, {})

    demonstrated_mentions = details.get("demonstrated_mentions", 0)
    skills_section_mentions = details.get("skills_section_mentions", 0)

    if demonstrated_mentions > 0:
        status = "matched"
        confidence: Confidence = "high"
        resume_evidence = (
            f"Resume demonstrates {skill} outside a skills-only listing "
            f"({demonstrated_mentions} mention(s))."
        )
        explanation = (
            f"{skill} is used in resume experience/project content, not "
            "just listed as a claimed skill."
        )
    elif skills_section_mentions > 0:
        status = "partial"
        confidence = "medium"
        resume_evidence = (
            f"Resume lists {skill} in a skills section but does not "
            "demonstrate its use elsewhere."
        )
        explanation = (
            f"{skill} is claimed but not shown being used in experience, "
            "project, or education content."
        )
    else:
        status = "missing"
        confidence = "high"
        resume_evidence = None
        explanation = f"No mention of {skill} was found anywhere in the resume."

    return RequirementAlignment(
        requirement_id=requirement.requirement_id,
        requirement_type=requirement.requirement_type,
        category=requirement.category,
        requirement_text=requirement.requirement_text,
        status=status,
        jd_evidence=requirement.jd_evidence,
        resume_evidence=resume_evidence,
        explanation=explanation,
        confidence=confidence,
        **_carry_requirement_metadata(requirement),
    )


# ---------------------------------------------------------------------------
# Experience alignment
# ---------------------------------------------------------------------------

def _evaluate_experience(
    requirement: JobRequirementItem,
    resume: ResumeEvidenceProfile,
) -> RequirementAlignment:
    minimum_years = requirement.minimum_years or 0.0
    years = resume.years_experience

    if years is None:
        status = "missing"
        confidence: Confidence = "low"
        resume_evidence = None
        explanation = (
            "The candidate's profile does not declare total years of "
            "experience, so this requirement cannot be verified."
        )
    elif years >= minimum_years:
        status = "matched"
        confidence = "high"
        resume_evidence = f"Profile declares {years:g} years of experience."
        explanation = (
            f"{years:g} years meets the required {minimum_years:g}+ years."
        )
    elif years > 0:
        status = "partial"
        confidence = "high"
        resume_evidence = f"Profile declares {years:g} years of experience."
        explanation = (
            f"{years:g} years is below the required {minimum_years:g}+ years."
        )
    else:
        status = "missing"
        confidence = "high"
        resume_evidence = None
        explanation = (
            f"Profile declares no years of experience; "
            f"{minimum_years:g}+ years are required."
        )

    return RequirementAlignment(
        requirement_id=requirement.requirement_id,
        requirement_type=requirement.requirement_type,
        category=requirement.category,
        requirement_text=requirement.requirement_text,
        status=status,
        jd_evidence=requirement.jd_evidence,
        resume_evidence=resume_evidence,
        explanation=explanation,
        confidence=confidence,
        **_carry_requirement_metadata(requirement),
    )


# ---------------------------------------------------------------------------
# Education alignment
# ---------------------------------------------------------------------------

# Intentionally a small, self-contained detection vocabulary for scanning
# unstructured resume prose — distinct in purpose from AJI-012's
# `_DEGREE_LABELS`/`_match_degree` (apps/api/services/job_intelligence/
# deterministic.py), which classify JD *clauses*, not resume text. Reusing
# that private, clause-oriented parser here would not fit this task (an
# open substring scan, not a clause classification), so it is not reused
# as-is; both are deliberately minimal, only recognizing explicit degree
# phrasing rather than inferring one.
_DEGREE_RANK: dict[str, int] = {
    "associate's": 1,
    "bachelor's": 2,
    "master's": 3,
    "mba": 3,
    "phd": 4,
}

_DEGREE_SEARCH_TERMS: dict[int, tuple[str, ...]] = {
    1: ("associate's degree", "associate degree", "a.a.", "a.s."),
    2: (
        "bachelor's degree",
        "bachelor degree",
        "bachelor's",
        "bachelors",
        "b.s.",
        "b.a.",
    ),
    3: (
        "master's degree",
        "master degree",
        "master's",
        "masters",
        "m.s.",
        "m.a.",
        "mba",
    ),
    4: ("ph.d", "phd", "doctorate", "doctoral"),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _highest_degree_found(raw_text_lower: str) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None

    for rank, phrases in _DEGREE_SEARCH_TERMS.items():
        for phrase in phrases:
            if phrase in raw_text_lower:
                if best is None or rank > best[0]:
                    best = (rank, phrase)
                break

    return best


def _evaluate_education(
    requirement: JobRequirementItem,
    resume: ResumeEvidenceProfile,
) -> RequirementAlignment:
    raw_text_lower = _normalize(resume.raw_text)
    required_rank = _DEGREE_RANK.get(
        (requirement.degree_level or "").strip().lower()
    )

    if required_rank is None:
        # No objective degree-level signal to verify against (AJI-012
        # only ever builds an EducationRequirement from a matched degree
        # token in practice, but the contract technically allows None —
        # this is a defensive fallback, not the common path).
        return RequirementAlignment(
            requirement_id=requirement.requirement_id,
            requirement_type=requirement.requirement_type,
            category=requirement.category,
            requirement_text=requirement.requirement_text,
            status="missing",
            jd_evidence=requirement.jd_evidence,
            resume_evidence=None,
            explanation=(
                "This education requirement has no explicit degree level "
                "to verify against the resume."
            ),
            confidence="low",
            **_carry_requirement_metadata(requirement),
        )

    found = _highest_degree_found(raw_text_lower)
    field_of_study = (requirement.field_of_study or "").strip()
    field_found = bool(field_of_study) and _normalize(field_of_study) in raw_text_lower

    if found is None:
        status = "missing"
        confidence: Confidence = "high"
        resume_evidence = None
        explanation = (
            f"No mention of a {requirement.degree_level} (or higher) degree "
            "was found in the resume."
        )
    elif found[0] >= required_rank:
        if field_of_study and not field_found:
            status = "partial"
            confidence = "medium"
            resume_evidence = f"Resume mentions '{found[1]}'."
            explanation = (
                f"Degree level meets the {requirement.degree_level} "
                f"requirement, but '{field_of_study}' was not confirmed "
                "in the resume."
            )
        else:
            status = "matched"
            confidence = "high"
            resume_evidence = f"Resume mentions '{found[1]}'" + (
                f" and '{field_of_study}'." if field_of_study else "."
            )
            explanation = (
                f"Resume degree level meets the {requirement.degree_level} "
                "requirement."
            )
    else:
        status = "partial"
        confidence = "high"
        resume_evidence = f"Resume mentions '{found[1]}'."
        explanation = (
            f"Resume shows a lower degree level than the required "
            f"{requirement.degree_level}."
        )

    return RequirementAlignment(
        requirement_id=requirement.requirement_id,
        requirement_type=requirement.requirement_type,
        category=requirement.category,
        requirement_text=requirement.requirement_text,
        status=status,
        jd_evidence=requirement.jd_evidence,
        resume_evidence=resume_evidence,
        explanation=explanation,
        confidence=confidence,
        **_carry_requirement_metadata(requirement),
    )


# ---------------------------------------------------------------------------
# Certification alignment
# ---------------------------------------------------------------------------

# AJI-012 stores the *whole JD clause* as CertificationRequirement.name
# (e.g. "AWS Certified Solutions Architect certification is required"),
# not a clean certification name — there is no canonical certification
# name vocabulary anywhere in this codebase to normalize against (unlike
# skills). Matching therefore compares the clause's own significant
# terms (i.e. the clause with generic requirement/certification
# boilerplate stripped) against the resume text, rather than inventing a
# new certification vocabulary.
_CERT_BOILERPLATE_WORDS = {
    "a", "active", "and", "are", "bonus", "certificate", "certificates",
    "certification", "certifications", "certified", "current", "desired",
    "have", "highly", "in", "is", "its", "must", "nice", "of", "or",
    "plus", "preferred", "required", "should", "strongly", "the", "to",
    "valid", "with",
}


def _significant_terms(text: str) -> list[str]:
    # A trailing sentence period would otherwise stick to the last word
    # in a clause (e.g. "...is required." -> "required."), which would
    # never match the boilerplate list below; strip only a *trailing*
    # period so an internal one (e.g. "Node.js", "M.S.") is preserved.
    words = [
        word.rstrip(".")
        for word in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]*", text)
    ]
    return [
        word
        for word in words
        if len(word) > 1 and word.lower() not in _CERT_BOILERPLATE_WORDS
    ]


def _evaluate_certification(
    requirement: JobRequirementItem,
    resume: ResumeEvidenceProfile,
) -> RequirementAlignment:
    raw_text_lower = _normalize(resume.raw_text)
    terms = _significant_terms(requirement.certification_name or "")

    if not terms:
        return RequirementAlignment(
            requirement_id=requirement.requirement_id,
            requirement_type=requirement.requirement_type,
            category=requirement.category,
            requirement_text=requirement.requirement_text,
            status="missing",
            jd_evidence=requirement.jd_evidence,
            resume_evidence=None,
            explanation=(
                "This certification requirement has no specific "
                "certification name to verify against the resume."
            ),
            confidence="low",
            **_carry_requirement_metadata(requirement),
        )

    matched_terms = [
        term
        for term in terms
        if re.search(
            rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])",
            raw_text_lower,
        )
    ]

    ratio = len(matched_terms) / len(terms)

    if ratio == 0:
        status = "missing"
        confidence: Confidence = "high"
        resume_evidence = None
        explanation = "No mention of this certification was found in the resume."
    elif ratio >= 0.8:
        status = "matched"
        confidence = "high" if ratio == 1.0 else "medium"
        resume_evidence = f"Resume mentions: {', '.join(matched_terms)}."
        explanation = "The certification's key terms are present in the resume."
    else:
        status = "partial"
        confidence = "medium"
        resume_evidence = f"Resume mentions: {', '.join(matched_terms)}."
        explanation = (
            "Only some of the certification's key terms were found in "
            "the resume."
        )

    return RequirementAlignment(
        requirement_id=requirement.requirement_id,
        requirement_type=requirement.requirement_type,
        category=requirement.category,
        requirement_text=requirement.requirement_text,
        status=status,
        jd_evidence=requirement.jd_evidence,
        resume_evidence=resume_evidence,
        explanation=explanation,
        confidence=confidence,
        **_carry_requirement_metadata(requirement),
    )


_EVALUATORS = {
    "skill": _evaluate_skill,
    "experience": _evaluate_experience,
    "education": _evaluate_education,
    "certification": _evaluate_certification,
}


def evaluate_ats_alignment(
    job_requirements: list[JobRequirementItem],
    resume: ResumeEvidenceProfile,
    *,
    relationships: list[RequirementRelationshipGroup] | None = None,
    screening_constraints: list[ScreeningConstraintInfo] | None = None,
) -> AtsAlignmentResult | None:
    """
    Evaluate every requirement independently and aggregate an overall
    score/confidence. Returns None when there are no requirements to
    evaluate at all (AJI-013 section 19: no score for invalid inputs) —
    the caller must not persist a fabricated result in that case.

    `relationships`/`screening_constraints` (AJI-020C) are pure
    passthrough onto the returned `AtsAlignmentResult` — see their
    dataclass docstrings in contracts.py for why neither ever
    participates in `overall_score`/`must_have_total`/`preferred_total`
    or any per-requirement `status` decided above.
    """
    if not job_requirements:
        return None

    requirement_results = [
        _EVALUATORS[requirement.requirement_type](requirement, resume)
        for requirement in job_requirements
    ]

    overall_score = compute_overall_score(requirement_results)
    overall_confidence = compute_overall_confidence(requirement_results)

    if overall_score is None or overall_confidence is None:
        return None

    must_have = [r for r in requirement_results if r.category == "must_have"]
    preferred = [r for r in requirement_results if r.category == "preferred"]

    return AtsAlignmentResult(
        overall_score=overall_score,
        confidence=overall_confidence,
        requirement_results=requirement_results,
        must_have_total=len(must_have),
        must_have_matched=sum(1 for r in must_have if r.status == "matched"),
        preferred_total=len(preferred),
        preferred_matched=sum(1 for r in preferred if r.status == "matched"),
        engine_version=ENGINE_VERSION,
        scoring_version=SCORING_VERSION,
        relationships=relationships or [],
        screening_constraints=screening_constraints or [],
    )
