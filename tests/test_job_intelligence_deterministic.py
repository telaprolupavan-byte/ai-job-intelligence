from apps.api.services.job_intelligence.deterministic import (
    RawJobDescription,
    extract_deterministic,
)


def _raw(**kwargs) -> RawJobDescription:
    defaults = dict(title="Software Engineer")
    defaults.update(kwargs)
    return RawJobDescription(**defaults)


# ---------------------------------------------------------------------------
# A. Job identity / seniority
# ---------------------------------------------------------------------------

def test_seniority_detected_from_title():
    result = extract_deterministic(_raw(title="Senior AI Engineer"))
    assert result.seniority == "Senior"


def test_seniority_staff_and_principal():
    assert extract_deterministic(_raw(title="Staff Engineer")).seniority == "Staff"
    assert (
        extract_deterministic(_raw(title="Principal Engineer")).seniority
        == "Principal"
    )


def test_seniority_intern():
    result = extract_deterministic(_raw(title="Software Engineering Intern"))
    assert result.seniority == "Intern"


def test_seniority_missing_from_ambiguous_title():
    result = extract_deterministic(_raw(title="AI Engineer"))
    assert result.seniority is None


def test_seniority_never_inferred_from_salary():
    result = extract_deterministic(
        _raw(title="AI Engineer", salary_min=250000, salary_max=300000)
    )
    assert result.seniority is None


# ---------------------------------------------------------------------------
# B. Employment
# ---------------------------------------------------------------------------

def test_employment_type_full_time():
    result = extract_deterministic(_raw(employment_type="Full-time"))
    assert result.employment.employment_type == "full_time"


def test_employment_type_contract():
    result = extract_deterministic(_raw(employment_type="Contractor"))
    assert result.employment.employment_type == "contract"


def test_employment_type_contract_to_hire():
    result = extract_deterministic(
        _raw(employment_type="Contract", description="This is a contract-to-hire position.")
    )
    assert result.employment.employment_type == "contract_to_hire"


def test_employment_type_internship():
    result = extract_deterministic(_raw(employment_type="Internship"))
    assert result.employment.employment_type == "internship"


def test_employment_type_unknown_when_not_disclosed():
    result = extract_deterministic(_raw())
    assert result.employment.employment_type == "unknown"


def test_employment_type_ambiguous_wording_stays_unknown():
    result = extract_deterministic(_raw(employment_type="Flexible"))
    assert result.employment.employment_type == "unknown"


# ---------------------------------------------------------------------------
# C. Location
# ---------------------------------------------------------------------------

def test_location_exact_city_state():
    result = extract_deterministic(_raw(location="New York, NY", country="USA"))
    assert result.location.city == "New York"
    assert result.location.state == "NY"
    assert result.location.country == "USA"


def test_location_remote():
    result = extract_deterministic(_raw(location="Remote - United States"))
    assert result.location.remote_type == "remote"
    assert result.location.work_arrangement_text == "Remote - United States"


def test_location_hybrid():
    result = extract_deterministic(_raw(location="Hybrid - Newark, NJ"))
    assert result.location.remote_type == "hybrid"
    assert result.location.city == "Newark"
    assert result.location.state == "NJ"


def test_location_onsite():
    result = extract_deterministic(_raw(remote_type="onsite", location="Austin, TX"))
    assert result.location.remote_type == "onsite"
    assert result.location.city == "Austin"


def test_location_multiple_locations():
    result = extract_deterministic(_raw(location="Multiple U.S. locations"))
    assert result.location.city is None
    assert result.location.raw_location == "Multiple U.S. locations"


def test_location_missing():
    result = extract_deterministic(_raw(location=None))
    assert result.location.raw_location is None
    assert result.location.city is None
    assert result.location.remote_type == "unknown"


def test_location_malformed_does_not_crash():
    result = extract_deterministic(_raw(location="???,,, ---"))
    assert result.location.raw_location == "???,,, ---"
    assert result.location.city is None


# ---------------------------------------------------------------------------
# D. Required vs preferred
# ---------------------------------------------------------------------------

def test_required_vs_preferred_python_pytorch():
    result = extract_deterministic(
        _raw(description="Python required; PyTorch preferred.")
    )

    required_skills = {item.canonical_skill for item in result.required_skills}
    preferred_skills = {item.canonical_skill for item in result.preferred_skills}

    assert required_skills == {"python"}
    assert preferred_skills == {"pytorch"}


def test_required_marker_must():
    result = extract_deterministic(_raw(description="Must have Java experience."))
    assert any(
        item.canonical_skill == "java" for item in result.required_skills
    )


def test_required_marker_minimum():
    result = extract_deterministic(
        _raw(description="Minimum of Docker experience needed.")
    )
    assert any(
        item.canonical_skill == "docker" for item in result.required_skills
    )


def test_preferred_marker_nice_to_have():
    result = extract_deterministic(
        _raw(description="Kubernetes experience is nice to have.")
    )
    assert any(
        item.canonical_skill == "kubernetes" for item in result.preferred_skills
    )


def test_preferred_marker_bonus():
    result = extract_deterministic(
        _raw(description="Experience with Terraform is a bonus.")
    )
    assert any(
        item.canonical_skill == "terraform" for item in result.preferred_skills
    )


def test_preferred_marker_plus():
    result = extract_deterministic(
        _raw(description="Rust knowledge is a plus.")
    )
    assert any(
        item.canonical_skill == "rust" for item in result.preferred_skills
    )


def test_preferred_never_promoted_to_required():
    result = extract_deterministic(
        _raw(
            description=(
                "Python required. Python is also nice to have for scripting."
            )
        )
    )

    required_skills = {item.canonical_skill for item in result.required_skills}
    preferred_skills = {item.canonical_skill for item in result.preferred_skills}

    assert "python" in required_skills
    assert "python" not in preferred_skills


def test_section_level_default_required():
    # No inline marker: everything before a "preferred qualifications"
    # section defaults to required.
    result = extract_deterministic(
        _raw(
            description=(
                "Experience with SQL databases.\n\n"
                "Preferred Qualifications:\n"
                "Experience with GraphQL."
            )
        )
    )

    required_skills = {item.canonical_skill for item in result.required_skills}
    preferred_skills = {item.canonical_skill for item in result.preferred_skills}

    assert "sql" in required_skills
    assert "graphql" in preferred_skills


# ---------------------------------------------------------------------------
# E. Skills / evidence
# ---------------------------------------------------------------------------

def test_skill_alias_normalization():
    result = extract_deterministic(
        _raw(description="3+ years of Python 3 development required.")
    )
    assert any(
        item.canonical_skill == "python" for item in result.required_skills
    )


def test_skill_llm_alias_group():
    result = extract_deterministic(
        _raw(description="Experience with Large Language Models required.")
    )
    assert any(item.canonical_skill == "llm" for item in result.required_skills)


def test_no_duplicate_skill_entries():
    result = extract_deterministic(
        _raw(
            description=(
                "Python required. Strong Python skills required. "
                "Python experience required."
            )
        )
    )
    python_entries = [
        item for item in result.required_skills if item.canonical_skill == "python"
    ]
    assert len(python_entries) == 1


def test_unknown_skill_not_invented():
    result = extract_deterministic(
        _raw(description="Experience with a proprietary internal tool required.")
    )
    assert result.required_skills == []


def test_skill_evidence_preserved():
    result = extract_deterministic(
        _raw(description="3+ years of Python development required.")
    )
    python_item = next(
        item for item in result.required_skills if item.canonical_skill == "python"
    )
    assert "Python" in python_item.evidence_text


# ---------------------------------------------------------------------------
# F. Experience
# ---------------------------------------------------------------------------

def test_experience_years_plus():
    result = extract_deterministic(
        _raw(description="3+ years of Python development required.")
    )
    assert result.required_experience[0].minimum_years == 3.0


def test_experience_years_exact():
    result = extract_deterministic(
        _raw(description="5 years experience with Java required.")
    )
    assert result.required_experience[0].minimum_years == 5.0


def test_experience_without_numeric_years_not_captured():
    result = extract_deterministic(
        _raw(description="Extensive experience with distributed systems required.")
    )
    assert result.required_experience == []


def test_experience_production_context():
    result = extract_deterministic(
        _raw(description="3+ years of production RAG development required.")
    )
    assert result.required_experience[0].context == "production"


def test_experience_leadership_context():
    result = extract_deterministic(
        _raw(description="5+ years of leadership experience required.")
    )
    assert result.required_experience[0].context == "leadership"


def test_experience_domain_area():
    result = extract_deterministic(
        _raw(description="3+ years building production ML systems required.")
    )
    assert result.required_experience[0].minimum_years == 3.0
    assert result.required_experience[0].context == "production"


def test_unrelated_numbers_not_treated_as_experience():
    result = extract_deterministic(
        _raw(description="Founded in 2018. Team of 50 engineers.")
    )
    assert result.required_experience == []
    assert result.preferred_experience == []


def test_experience_preferred_classification():
    result = extract_deterministic(
        _raw(description="5+ years of Kubernetes experience preferred.")
    )
    assert result.preferred_experience[0].minimum_years == 5.0
    assert result.required_experience == []


# ---------------------------------------------------------------------------
# G. Education
# ---------------------------------------------------------------------------

def test_education_required_degree_with_field():
    result = extract_deterministic(
        _raw(description="BS in Computer Science required.")
    )
    item = result.education[0]
    assert item.level == "required"
    assert item.degree_level == "Bachelor's"
    assert item.field_of_study == "Computer Science"


def test_education_preferred_degree():
    result = extract_deterministic(_raw(description="Master's preferred."))
    item = result.education[0]
    assert item.level == "preferred"
    assert item.degree_level == "Master's"


def test_education_missing():
    result = extract_deterministic(
        _raw(description="Strong communication skills required.")
    )
    assert result.education == []


def test_education_phd():
    result = extract_deterministic(
        _raw(description="PhD in Machine Learning required.")
    )
    item = result.education[0]
    assert item.degree_level == "PhD"


# ---------------------------------------------------------------------------
# H. Certifications
# ---------------------------------------------------------------------------

def test_certification_required():
    result = extract_deterministic(
        _raw(description="AWS certification is required for this role.")
    )
    assert result.certifications[0].level == "required"


def test_certification_preferred():
    result = extract_deterministic(
        _raw(description="AWS certification is a plus.")
    )
    assert result.certifications[0].level == "preferred"


def test_certification_missing():
    result = extract_deterministic(_raw(description="Great communication skills."))
    assert result.certifications == []


# ---------------------------------------------------------------------------
# I. Responsibilities are separate from requirements
# ---------------------------------------------------------------------------

def test_responsibilities_never_become_requirements():
    result = extract_deterministic(
        _raw(
            description="Python required.",
            responsibilities="- Build RAG pipelines\n- Own model deployment",
        )
    )

    responsibility_descriptions = {
        item.description for item in result.responsibilities
    }

    assert responsibility_descriptions == {
        "Build RAG pipelines",
        "Own model deployment",
    }

    # None of the requirement lists should contain responsibility text.
    required_skill_evidence = " ".join(
        item.evidence_text for item in result.required_skills
    )
    assert "RAG pipelines" not in required_skill_evidence


def test_responsibilities_empty_when_not_provided():
    result = extract_deterministic(_raw(responsibilities=None))
    assert result.responsibilities == []


# ---------------------------------------------------------------------------
# J. Authorization
# ---------------------------------------------------------------------------

def test_authorization_sponsorship_available():
    result = extract_deterministic(
        _raw(description="Visa sponsorship is available for this role.")
    )
    assert result.authorization.sponsorship == "available"


def test_authorization_sponsorship_unavailable():
    result = extract_deterministic(
        _raw(description="We are unable to sponsor work visas at this time.")
    )
    assert result.authorization.sponsorship == "unavailable"


def test_authorization_sponsorship_unknown_by_default():
    result = extract_deterministic(_raw(description="Great team culture."))
    assert result.authorization.sponsorship == "unknown"


def test_authorization_citizenship_required():
    result = extract_deterministic(
        _raw(description="U.S. citizenship is required for this position.")
    )
    assert result.authorization.citizenship == "required"


def test_authorization_citizenship_preferred():
    result = extract_deterministic(
        _raw(description="U.S. citizenship preferred.")
    )
    assert result.authorization.citizenship == "preferred"


def test_authorization_clearance_required():
    result = extract_deterministic(
        _raw(description="Active security clearance required.")
    )
    assert result.authorization.clearance == "required"


def test_authorization_clearance_preferred():
    result = extract_deterministic(
        _raw(description="Security clearance is preferred but not required.")
    )
    assert result.authorization.clearance == "preferred"


def test_authorization_generic_language():
    result = extract_deterministic(
        _raw(description="Must be authorized to work in the United States.")
    )
    assert result.authorization.work_authorization == "explicit_requirement"


def test_authorization_ambiguous_language_stays_unknown():
    result = extract_deterministic(
        _raw(description="We value diversity and international perspectives.")
    )
    assert result.authorization.sponsorship == "unknown"
    assert result.authorization.citizenship == "unknown"
    assert result.authorization.clearance == "unknown"
    assert result.authorization.work_authorization == "unknown"


# ---------------------------------------------------------------------------
# K. Compensation
# ---------------------------------------------------------------------------

def test_compensation_salary_range():
    result = extract_deterministic(
        _raw(salary_min=120000, salary_max=150000, salary_currency="USD")
    )
    assert result.compensation.salary_min == 120000
    assert result.compensation.salary_max == 150000
    assert result.compensation.period == "annual"


def test_compensation_hourly_range():
    result = extract_deterministic(
        _raw(
            salary_min=50,
            salary_max=75,
            salary_currency="USD",
            contract_worker_type="hourly",
        )
    )
    assert result.compensation.period == "hourly"


def test_compensation_missing():
    result = extract_deterministic(_raw())
    assert result.compensation.salary_min is None
    assert result.compensation.salary_max is None
    assert result.compensation.period == "unknown"


def test_compensation_currency_preserved():
    result = extract_deterministic(
        _raw(salary_min=100000, salary_max=120000, salary_currency="CAD")
    )
    assert result.compensation.currency == "CAD"
