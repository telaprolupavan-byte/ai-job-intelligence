"""Unit tests for the pure, DB-free ATS Alignment engine (AJI-013)."""

from services.ats_alignment.contracts import JobRequirementItem
from services.ats_alignment.engine import evaluate_ats_alignment
from services.ats_alignment.resume_adapter import ResumeEvidenceProfile
from services.ats_alignment.scoring import (
    compute_overall_confidence,
    compute_overall_score,
)


def make_resume(
    *,
    skill_evidence: dict | None = None,
    years_experience: float | None = None,
    raw_text: str = "",
) -> ResumeEvidenceProfile:
    return ResumeEvidenceProfile(
        raw_text=raw_text,
        skills=list((skill_evidence or {}).keys()),
        skill_evidence=skill_evidence or {},
        years_experience=years_experience,
    )


def skill_requirement(
    skill: str,
    *,
    category: str = "must_have",
    evidence: str = "Python required.",
) -> JobRequirementItem:
    return JobRequirementItem(
        requirement_id=f"skill:{skill}",
        requirement_type="skill",
        category=category,
        requirement_text=skill,
        jd_evidence=evidence,
        canonical_skill=skill,
    )


def experience_requirement(
    minimum_years: float,
    *,
    category: str = "must_have",
    area: str | None = None,
) -> JobRequirementItem:
    return JobRequirementItem(
        requirement_id=f"experience:0:{area or 'general'}",
        requirement_type="experience",
        category=category,
        requirement_text=f"{minimum_years}+ years",
        jd_evidence=f"{minimum_years}+ years of experience required.",
        minimum_years=minimum_years,
        area=area,
    )


def education_requirement(
    degree_level: str,
    *,
    field_of_study: str | None = None,
    category: str = "must_have",
) -> JobRequirementItem:
    return JobRequirementItem(
        requirement_id="education:0",
        requirement_type="education",
        category=category,
        requirement_text=degree_level,
        jd_evidence=f"{degree_level} required.",
        degree_level=degree_level,
        field_of_study=field_of_study,
    )


def certification_requirement(
    clause: str,
    *,
    category: str = "must_have",
) -> JobRequirementItem:
    return JobRequirementItem(
        requirement_id="certification:0",
        requirement_type="certification",
        category=category,
        requirement_text=clause,
        jd_evidence=clause,
        certification_name=clause,
    )


# ---------------------------------------------------------------------------
# Skill matching: exact / demonstrated / partial / missing
# ---------------------------------------------------------------------------

def test_skill_demonstrated_outside_skills_section_is_matched():
    requirement = skill_requirement("python")
    resume = make_resume(
        skill_evidence={
            "python": {
                "demonstrated_mentions": 2,
                "skills_section_mentions": 1,
            }
        }
    )

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "matched"
    assert result.requirement_results[0].confidence == "high"
    assert result.requirement_results[0].resume_evidence is not None


def test_skill_listed_only_in_skills_section_is_partial():
    requirement = skill_requirement("pytorch")
    resume = make_resume(
        skill_evidence={
            "pytorch": {
                "demonstrated_mentions": 0,
                "skills_section_mentions": 1,
            }
        }
    )

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "partial"
    assert result.requirement_results[0].confidence == "medium"


def test_skill_absent_entirely_is_missing():
    requirement = skill_requirement("kubernetes")
    resume = make_resume(skill_evidence={})

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "missing"
    assert result.requirement_results[0].resume_evidence is None


def test_multiple_skill_requirements_each_get_independent_results():
    requirements = [
        skill_requirement("python"),
        skill_requirement("kubernetes", category="preferred"),
    ]
    resume = make_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 3, "skills_section_mentions": 1},
        }
    )

    result = evaluate_ats_alignment(requirements, resume)

    statuses = {r.requirement_id: r.status for r in result.requirement_results}
    assert statuses["skill:python"] == "matched"
    assert statuses["skill:kubernetes"] == "missing"
    assert len(result.requirement_results) == 2


def test_must_have_and_preferred_categories_stay_distinct():
    requirements = [
        skill_requirement("python", category="must_have"),
        skill_requirement("go", category="preferred"),
    ]
    resume = make_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 1, "skills_section_mentions": 0},
            "go": {"demonstrated_mentions": 1, "skills_section_mentions": 0},
        }
    )

    result = evaluate_ats_alignment(requirements, resume)

    assert result.must_have_total == 1
    assert result.must_have_matched == 1
    assert result.preferred_total == 1
    assert result.preferred_matched == 1

    categories = {r.requirement_id: r.category for r in result.requirement_results}
    assert categories["skill:python"] == "must_have"
    assert categories["skill:go"] == "preferred"


# ---------------------------------------------------------------------------
# Experience matching
# ---------------------------------------------------------------------------

def test_experience_meeting_minimum_is_matched():
    requirement = experience_requirement(5)
    resume = make_resume(years_experience=6)

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "matched"
    assert result.requirement_results[0].confidence == "high"


def test_experience_below_minimum_is_partial():
    requirement = experience_requirement(5)
    resume = make_resume(years_experience=3)

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "partial"


def test_experience_with_no_profile_data_is_missing_low_confidence():
    requirement = experience_requirement(5)
    resume = make_resume(years_experience=None)

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "missing"
    assert result.requirement_results[0].confidence == "low"


def test_experience_of_zero_years_is_missing():
    requirement = experience_requirement(5)
    resume = make_resume(years_experience=0)

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "missing"


def test_experience_requirement_without_minimum_years_is_excluded_upstream():
    # The service-layer mapper skips ExperienceRequirement entries with no
    # minimum_years before calling the engine; the engine itself only
    # ever receives requirements that are objectively comparable.
    requirement = experience_requirement(0)
    requirement.minimum_years = None
    resume = make_resume(years_experience=5)

    result = evaluate_ats_alignment([requirement], resume)

    # minimum_years=None is treated as "0+ years" (trivially satisfied)
    # rather than crashing — defensive behavior, not the expected path.
    assert result.requirement_results[0].status == "matched"


# ---------------------------------------------------------------------------
# Education matching
# ---------------------------------------------------------------------------

def test_education_exact_degree_and_field_is_matched():
    requirement = education_requirement(
        "Bachelor's", field_of_study="Computer Science"
    )
    resume = make_resume(
        raw_text="Bachelor's degree in Computer Science from State University."
    )

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "matched"


def test_education_higher_degree_satisfies_lower_requirement():
    requirement = education_requirement("Bachelor's")
    resume = make_resume(raw_text="Master's degree in Data Science.")

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "matched"


def test_education_lower_degree_than_required_is_partial():
    requirement = education_requirement("Master's")
    resume = make_resume(raw_text="Bachelor's degree in Computer Science.")

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "partial"


def test_education_right_degree_wrong_field_is_partial():
    requirement = education_requirement(
        "Bachelor's", field_of_study="Mechanical Engineering"
    )
    resume = make_resume(raw_text="Bachelor's degree in Computer Science.")

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "partial"
    assert result.requirement_results[0].confidence == "medium"


def test_education_no_degree_mentioned_is_missing():
    requirement = education_requirement("Bachelor's")
    resume = make_resume(raw_text="Experienced software engineer.")

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "missing"


# ---------------------------------------------------------------------------
# Certification matching
# ---------------------------------------------------------------------------

def test_certification_present_is_matched():
    requirement = certification_requirement(
        "AWS Certified Solutions Architect certification is required."
    )
    resume = make_resume(
        raw_text="Holds AWS Certified Solutions Architect credential."
    )

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "matched"


def test_certification_absent_is_missing():
    requirement = certification_requirement(
        "PMP certification is required."
    )
    resume = make_resume(raw_text="Experienced project coordinator.")

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "missing"


def test_certification_partially_present_is_partial():
    requirement = certification_requirement(
        "Certified Kubernetes Application Developer certification preferred."
    )
    resume = make_resume(raw_text="Experience with Kubernetes clusters.")

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].status == "partial"


# ---------------------------------------------------------------------------
# Evidence rules
# ---------------------------------------------------------------------------

def test_matched_skill_always_carries_resume_evidence():
    requirement = skill_requirement("python")
    resume = make_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 1, "skills_section_mentions": 0}
        }
    )

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].resume_evidence
    assert "python" in result.requirement_results[0].resume_evidence.lower()


def test_missing_status_never_fabricates_resume_evidence():
    requirement = skill_requirement("rust")
    resume = make_resume(skill_evidence={})

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].resume_evidence is None


def test_jd_evidence_is_always_preserved_verbatim():
    requirement = skill_requirement("python", evidence="5+ years of Python.")
    resume = make_resume(skill_evidence={})

    result = evaluate_ats_alignment([requirement], resume)

    assert result.requirement_results[0].jd_evidence == "5+ years of Python."


def test_no_requirements_are_silently_ignored():
    requirements = [
        skill_requirement("python"),
        experience_requirement(3),
        education_requirement("Bachelor's"),
        certification_requirement("PMP required."),
    ]
    resume = make_resume(years_experience=1, raw_text="")

    result = evaluate_ats_alignment(requirements, resume)

    assert len(result.requirement_results) == len(requirements)
    assert {r.requirement_id for r in result.requirement_results} == {
        r.requirement_id for r in requirements
    }


# ---------------------------------------------------------------------------
# Scoring: deterministic aggregation, boundary conditions
# ---------------------------------------------------------------------------

def test_score_all_matched_with_bare_resume_is_capped_by_structure():
    # AJI-020: with a single matched must-have skill and no other JD
    # requirements, Requirement Coverage/Keyword Alignment/Evidence &
    # Experience are all 100, but this resume's raw_text is empty, so it
    # fails 4 of 5 Structure & Parseability checks (only
    # "consistent_heading_style" passes, since no
    # heading_style_inconsistency finding exists on empty text) ->
    # structure = 20. Weighted sum = 40 + 25 + 25 + (0.1 * 20) = 92,
    # under the must-have ceiling (100), so it is not capped further.
    # See test_ats_scoring_engine.py for full weighted-formula coverage,
    # including a fully-structured resume that reaches exactly 100.
    requirement = skill_requirement("python")
    resume = make_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 1, "skills_section_mentions": 0}
        }
    )

    result = evaluate_ats_alignment([requirement], resume)

    assert result.overall_score == 92.0


def test_score_all_missing_is_0():
    requirement = skill_requirement("python")
    resume = make_resume(skill_evidence={})

    result = evaluate_ats_alignment([requirement], resume)

    assert result.overall_score == 0.0


def test_score_mixed_matched_partial_missing():
    requirements = [
        skill_requirement("python"),  # matched -> 1.0
        skill_requirement("go"),  # partial -> 0.5
        skill_requirement("rust"),  # missing -> 0.0
    ]
    resume = make_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 1, "skills_section_mentions": 0},
            "go": {"demonstrated_mentions": 0, "skills_section_mentions": 1},
        }
    )

    result = evaluate_ats_alignment(requirements, resume)

    # (1.0 + 0.5 + 0.0) / 3 * 100 = 50.0
    assert result.overall_score == 50.0


def test_no_score_when_no_requirements():
    resume = make_resume()

    result = evaluate_ats_alignment([], resume)

    assert result is None


def test_compute_overall_score_empty_list_returns_none():
    resume = make_resume()
    assert compute_overall_score([], [], resume) is None


def test_compute_overall_confidence_empty_list_returns_none():
    assert compute_overall_confidence([]) is None


def test_engine_version_and_scoring_version_are_recorded():
    requirement = skill_requirement("python")
    resume = make_resume(
        skill_evidence={
            "python": {"demonstrated_mentions": 1, "skills_section_mentions": 0}
        }
    )

    result = evaluate_ats_alignment([requirement], resume)

    assert result.engine_version
    assert result.scoring_version
