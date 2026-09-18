"""Unit tests for the AJI-020 weighted ATS Alignment scoring engine.

`tests/test_ats_alignment_engine.py` (AJI-013) covers per-requirement
evidence evaluation (skill/experience/education/certification
matched/partial/missing verdicts), which AJI-020 does not change. This
file covers the score *aggregation* formula AJI-020 replaced the AJI-013
placeholder with: the four weighted components (Requirement Coverage 40%,
Keyword & Terminology Alignment 25%, Resume Evidence & Experience 25%,
Structure & Parseability 10%), the required-requirement guardrail, score
bounds, determinism, and resume-length neutrality.
"""

from services.ats_alignment.contracts import JobRequirementItem, RequirementAlignment
from services.ats_alignment.engine import _EVALUATORS, evaluate_ats_alignment
from services.ats_alignment.resume_adapter import (
    ResumeEvidenceProfile,
    build_resume_evidence_profile,
)
from services.ats_alignment.scoring import (
    compute_evidence_experience,
    compute_keyword_alignment,
    compute_must_have_ceiling,
    compute_overall_score,
    compute_requirement_coverage,
    compute_structure_parseability,
)
from services.ats_alignment.weights import SCORE_WEIGHTS

from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def skill_requirement(
    skill: str,
    *,
    category: str = "must_have",
) -> JobRequirementItem:
    return JobRequirementItem(
        requirement_id=f"skill:{skill}",
        requirement_type="skill",
        category=category,
        requirement_text=skill,
        jd_evidence=f"{skill} required.",
        canonical_skill=skill,
    )


def experience_requirement(
    minimum_years: float,
    *,
    category: str = "must_have",
) -> JobRequirementItem:
    return JobRequirementItem(
        requirement_id="experience:0:general",
        requirement_type="experience",
        category=category,
        requirement_text=f"{minimum_years}+ years",
        jd_evidence=f"{minimum_years}+ years required.",
        minimum_years=minimum_years,
    )


def education_requirement(degree_level: str, *, category: str = "must_have"):
    return JobRequirementItem(
        requirement_id="education:0",
        requirement_type="education",
        category=category,
        requirement_text=degree_level,
        jd_evidence=f"{degree_level} required.",
        degree_level=degree_level,
    )


def bare_resume(
    *,
    skill_evidence: dict | None = None,
    years_experience: float | None = None,
    skills: list[str] | None = None,
) -> ResumeEvidenceProfile:
    """A minimal, hand-built profile (no structural signals) — used when
    a test only cares about coverage/keyword/evidence components, not
    structure."""
    return ResumeEvidenceProfile(
        raw_text="",
        skills=skills if skills is not None else list((skill_evidence or {}).keys()),
        skill_evidence=skill_evidence or {},
        years_experience=years_experience,
    )


FULLY_STRUCTURED_RESUME = """Jordan Doe
jordan.doe@example.com
(555) 123-4567

Summary
Backend engineer focused on distributed systems.

Experience
- Built and deployed Python microservices on Kubernetes at scale.
- Led migration of legacy services to AWS with zero downtime.

Education
Bachelor's degree in Computer Science from State University.

Skills
Python, Kubernetes, AWS, Docker
"""


def full_resume(
    raw_text: str = FULLY_STRUCTURED_RESUME,
    *,
    years_experience: float | None = None,
) -> ResumeEvidenceProfile:
    analysis = analyze_resume_deterministically(raw_text)
    return build_resume_evidence_profile(
        analysis, raw_text=raw_text, years_experience=years_experience
    )


# ---------------------------------------------------------------------------
# Centralized weights
# ---------------------------------------------------------------------------

def test_weights_sum_to_one():
    assert round(sum(SCORE_WEIGHTS.values()), 10) == 1.0


def test_weights_match_approved_baseline():
    assert SCORE_WEIGHTS["requirement_coverage"] == 0.40
    assert SCORE_WEIGHTS["keyword_terminology_alignment"] == 0.25
    assert SCORE_WEIGHTS["resume_evidence_experience"] == 0.25
    assert SCORE_WEIGHTS["structure_parseability"] == 0.10


# ---------------------------------------------------------------------------
# Requirement Coverage (40%)
# ---------------------------------------------------------------------------

def test_requirement_coverage_all_matched_is_100():
    results = [
        RequirementAlignment(
            requirement_id="skill:python",
            requirement_type="skill",
            category="must_have",
            requirement_text="python",
            status="matched",
            jd_evidence="",
            resume_evidence="x",
            explanation="",
            confidence="high",
        )
    ]

    component = compute_requirement_coverage(results)
    assert component.score == 100.0
    assert component.weight == SCORE_WEIGHTS["requirement_coverage"]


def test_requirement_coverage_mixed_statuses():
    requirements = [
        skill_requirement("python"),
        skill_requirement("go"),
        skill_requirement("rust"),
    ]
    resume = bare_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 1, "skills_section_mentions": 0},
            "go": {"demonstrated_mentions": 0, "skills_section_mentions": 1},
        }
    )
    results = [
        _EVALUATORS[r.requirement_type](r, resume) for r in requirements
    ]

    component = compute_requirement_coverage(results)
    # (1.0 + 0.5 + 0.0) / 3 * 100
    assert component.score == 50.0


# ---------------------------------------------------------------------------
# Keyword & Terminology Alignment (25%)
# ---------------------------------------------------------------------------

def test_keyword_alignment_full_overlap():
    job_requirements = [skill_requirement("python"), skill_requirement("kubernetes")]
    resume = bare_resume(skills=["python", "kubernetes"])

    component = compute_keyword_alignment(job_requirements, resume)
    assert component.score == 100.0


def test_keyword_alignment_partial_overlap():
    job_requirements = [
        skill_requirement("python"),
        skill_requirement("kubernetes"),
        skill_requirement("rust"),
        skill_requirement("go"),
    ]
    resume = bare_resume(skills=["python", "kubernetes"])

    component = compute_keyword_alignment(job_requirements, resume)
    assert component.score == 50.0


def test_keyword_alignment_no_skill_requirements_is_full_credit():
    job_requirements = [experience_requirement(3)]
    resume = bare_resume(skills=[])

    component = compute_keyword_alignment(job_requirements, resume)
    assert component.score == 100.0


def test_keyword_alignment_acronym_and_semantic_aliases_resolve_upstream():
    # "GCP" and "Google Cloud Platform" both canonicalize to "gcp" via
    # services.skills before either side reaches this function — this
    # test asserts the keyword scorer trusts that canonical identity
    # rather than doing its own string comparison.
    job_requirements = [skill_requirement("gcp")]
    resume_analysis_skills = ["gcp"]  # what find_skills() would return
    # for resume text mentioning "Google Cloud Platform".
    resume = bare_resume(skills=resume_analysis_skills)

    component = compute_keyword_alignment(job_requirements, resume)
    assert component.score == 100.0


def test_keyword_alignment_never_conflates_related_but_different_skills():
    # "python" and "pytorch" are both real, curated canonical skills
    # (services.skills.CANONICAL_SKILLS) with no shared alias between
    # them — a resume that only has "pytorch" must never be credited for
    # a "python" requirement.
    job_requirements = [skill_requirement("python")]
    resume = bare_resume(skills=["pytorch"])

    component = compute_keyword_alignment(job_requirements, resume)
    assert component.score == 0.0


# ---------------------------------------------------------------------------
# Resume Evidence & Experience (25%)
# ---------------------------------------------------------------------------

def test_evidence_experience_demonstrated_skill_scores_full():
    requirement = skill_requirement("python")
    resume = bare_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 2, "skills_section_mentions": 0}
        }
    )

    results = [_EVALUATORS["skill"](requirement, resume)]

    component = compute_evidence_experience(results)
    assert component.score == 100.0


def test_evidence_experience_skills_section_only_scores_half():
    requirement = skill_requirement("python")
    resume = bare_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 0, "skills_section_mentions": 1}
        }
    )

    results = [_EVALUATORS["skill"](requirement, resume)]

    component = compute_evidence_experience(results)
    assert component.score == 50.0


def test_evidence_experience_excludes_education_and_certification():

    edu_requirement = education_requirement("Bachelor's")
    resume = bare_resume()
    resume.raw_text = "No degree mentioned."
    results = [_EVALUATORS["education"](edu_requirement, resume)]

    # No skill/experience requirements present -> nothing to check ->
    # full credit, regardless of the (irrelevant) missing education match.
    component = compute_evidence_experience(results)
    assert component.score == 100.0


def test_evidence_experience_below_minimum_years_is_partial():

    requirement = experience_requirement(5)
    resume = bare_resume(years_experience=2)
    results = [_EVALUATORS["experience"](requirement, resume)]

    component = compute_evidence_experience(results)
    assert component.score == 50.0


# ---------------------------------------------------------------------------
# Structure & Parseability (10%)
# ---------------------------------------------------------------------------

def test_structure_fully_structured_resume_is_100():
    resume = full_resume()
    component = compute_structure_parseability(resume)
    assert component.score == 100.0


def test_structure_bare_resume_scores_low():
    resume = bare_resume()
    component = compute_structure_parseability(resume)
    # Only "consistent_heading_style" passes trivially on empty text.
    assert component.score == 20.0


def test_structure_missing_contact_info_only():
    raw_text = FULLY_STRUCTURED_RESUME.replace(
        "jordan.doe@example.com\n(555) 123-4567\n", ""
    )
    resume = full_resume(raw_text)
    component = compute_structure_parseability(resume)
    assert component.score == 80.0


def test_structure_score_is_independent_of_resume_length():
    padded = FULLY_STRUCTURED_RESUME + (
        "\n- Additional accomplishment bullet describing more work.\n" * 40
    )

    short_component = compute_structure_parseability(full_resume())
    padded_component = compute_structure_parseability(full_resume(padded))

    assert short_component.score == padded_component.score == 100.0


# ---------------------------------------------------------------------------
# Required-requirement guardrail
# ---------------------------------------------------------------------------

def test_must_have_ceiling_caps_overall_score():
    # A missing must-have skill, but perfect preferred/keyword/structure
    # signals elsewhere, must not produce a high overall score.
    requirements = [
        skill_requirement("rust", category="must_have"),  # not in the resume
        skill_requirement("python", category="preferred"),
    ]
    resume = full_resume()  # demonstrates "python", never mentions "rust"

    result = evaluate_ats_alignment(requirements, resume)

    assert result.must_have_ceiling == 0.0
    assert result.overall_score == 0.0


def test_must_have_ceiling_is_none_when_no_must_have_requirements():
    requirements = [skill_requirement("python", category="preferred")]
    resume = full_resume()

    ceiling = compute_must_have_ceiling(
        evaluate_ats_alignment(requirements, resume).requirement_results
    )

    assert ceiling is None


def test_must_have_ceiling_recorded_on_result():
    requirements = [skill_requirement("python", category="must_have")]
    resume = full_resume()

    result = evaluate_ats_alignment(requirements, resume)

    assert result.must_have_ceiling == 100.0


def test_partial_must_have_coverage_caps_score_between_bounds():
    requirements = [
        skill_requirement("python", category="must_have"),  # matched
        skill_requirement("rust", category="must_have"),  # missing
    ]
    resume = full_resume()

    result = evaluate_ats_alignment(requirements, resume)

    # must-have coverage: (1.0 + 0.0) / 2 * 100 = 50
    assert result.must_have_ceiling == 50.0
    assert result.overall_score <= 50.0


# ---------------------------------------------------------------------------
# Score bounds and determinism
# ---------------------------------------------------------------------------

def test_overall_score_is_never_negative_or_over_100():
    scenarios = [
        ([skill_requirement("python")], bare_resume()),
        ([skill_requirement("python")], full_resume()),
        (
            [
                skill_requirement("python"),
                experience_requirement(10),
                education_requirement("PhD"),
            ],
            bare_resume(years_experience=0),
        ),
    ]

    for requirements, resume in scenarios:
        result = evaluate_ats_alignment(requirements, resume)
        assert 0.0 <= result.overall_score <= 100.0


def test_scoring_is_deterministic_across_repeated_calls():
    requirements = [
        skill_requirement("python", category="must_have"),
        skill_requirement("kubernetes", category="preferred"),
        experience_requirement(3),
    ]
    resume = full_resume(years_experience=5)

    first = evaluate_ats_alignment(requirements, resume)
    second = evaluate_ats_alignment(requirements, resume)

    assert first.overall_score == second.overall_score
    assert [c.score for c in first.components] == [c.score for c in second.components]


def test_components_always_has_four_entries():
    requirements = [skill_requirement("python")]
    resume = full_resume()

    result = evaluate_ats_alignment(requirements, resume)

    assert len(result.components) == 4
    assert {c.name for c in result.components} == set(SCORE_WEIGHTS.keys())


def test_overall_score_equals_weighted_component_sum_when_uncapped():
    requirements = [
        skill_requirement("python", category="preferred"),
        skill_requirement("kubernetes", category="preferred"),
    ]
    resume = full_resume()

    result = evaluate_ats_alignment(requirements, resume)

    # No must-have requirements -> no ceiling applied.
    assert result.must_have_ceiling is None
    expected = round(sum(c.weighted_score for c in result.components), 2)
    assert result.overall_score == expected


# ---------------------------------------------------------------------------
# Resume-length neutrality (end-to-end, not just the structure component)
# ---------------------------------------------------------------------------

def test_overall_score_is_unaffected_by_resume_length():
    requirements = [
        skill_requirement("python", category="must_have"),
        experience_requirement(3, category="must_have"),
    ]

    short_resume = full_resume(years_experience=5)
    padded_text = FULLY_STRUCTURED_RESUME * 5
    long_resume = full_resume(padded_text, years_experience=5)

    short_result = evaluate_ats_alignment(requirements, short_resume)
    long_result = evaluate_ats_alignment(requirements, long_resume)

    assert short_result.overall_score == long_result.overall_score
