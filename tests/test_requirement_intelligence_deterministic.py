from apps.api.services.requirement_intelligence.deterministic import (
    RawRequirementSource,
    extract_deterministic,
    find_protected_skills,
    split_clauses_with_spans,
)


def _requirements(text: str, **kwargs) -> RawRequirementSource:
    return RawRequirementSource(title=kwargs.pop("title", "Engineer"), requirements=text, **kwargs)


def _by_id(result, item_id):
    return next(item for item in result.requirements if item.id == item_id)


def _skills(result):
    return {
        term: item
        for item in result.requirements
        if item.requirement_type == "skill"
        for term in item.canonical_terms
    }


# ---------------------------------------------------------------------------
# Clause splitting / provenance spans
# ---------------------------------------------------------------------------

def test_split_clauses_with_spans_returns_accurate_offsets():
    text = "Python required. Java preferred; Go is a plus"
    clauses = split_clauses_with_spans(text)

    assert [c.text for c in clauses] == [
        "Python required",
        "Java preferred",
        "Go is a plus",
    ]

    for clause in clauses:
        assert text[clause.start:clause.end] == clause.text


def test_split_clauses_strips_bullets_and_tracks_offset():
    text = "- Build APIs\n- Mentor engineers"
    clauses = split_clauses_with_spans(text)

    assert clauses[0].text == "Build APIs"
    assert text[clauses[0].start:clauses[0].end] == "Build APIs"


def test_requirement_item_provenance_matches_raw_source_text():
    raw = _requirements("5+ years of Python experience required.")
    result = extract_deterministic(raw)

    full_text = "\n".join(
        part for part in [raw.description, raw.requirements, raw.responsibilities] if part
    )

    for item in result.requirements:
        if item.source_span is None:
            continue
        span = item.source_span
        assert full_text[span.start:span.end] == span.text


# ---------------------------------------------------------------------------
# Requirement types + four-tier importance
# ---------------------------------------------------------------------------

def test_required_skill_is_classified_required():
    result = extract_deterministic(_requirements("Python is required."))
    item = _skills(result)["python"]
    assert item.importance == "required"
    assert item.confidence == "high"


def test_preferred_skill_is_classified_preferred():
    result = extract_deterministic(_requirements("Docker experience preferred."))
    item = _skills(result)["docker"]
    assert item.importance == "preferred"


def test_contextual_mention_is_not_a_requirement():
    result = extract_deterministic(
        _requirements("Our backend is built with Go and Kubernetes.")
    )
    skills = _skills(result)
    assert skills["go"].importance == "contextual"
    assert skills["kubernetes"].importance == "contextual"


def test_informational_section_is_never_a_requirement():
    result = extract_deterministic(
        _requirements(
            "Requirements:\nPython required.\n"
            "Benefits:\nWe offer React training and free snacks."
        )
    )
    skills = _skills(result)
    assert skills["python"].importance == "required"
    assert skills["react"].importance == "informational"


def test_default_tier_is_required_absent_markers():
    result = extract_deterministic(_requirements("Kubernetes"))
    assert _skills(result)["kubernetes"].importance == "required"


# ---------------------------------------------------------------------------
# Hard requirements
# ---------------------------------------------------------------------------

def test_must_have_marker_sets_hard_requirement():
    result = extract_deterministic(_requirements("Must have AWS experience."))
    item = _skills(result)["aws"]
    assert item.importance == "required"
    assert item.hard_requirement is True


def test_bare_required_marker_is_not_hard():
    result = extract_deterministic(_requirements("AWS experience is required."))
    item = _skills(result)["aws"]
    assert item.importance == "required"
    assert item.hard_requirement is False


def test_preferred_items_are_never_hard():
    result = extract_deterministic(_requirements("AWS experience preferred."))
    item = _skills(result)["aws"]
    assert item.hard_requirement is False


# ---------------------------------------------------------------------------
# AND / OR / MIN_COUNT / EQUIVALENT relationships
# ---------------------------------------------------------------------------

def test_or_clause_creates_or_group():
    result = extract_deterministic(
        _requirements("Python or Java experience is required.")
    )
    or_groups = [g for g in result.relationships if g.relationship == "OR"]
    assert len(or_groups) == 1
    member_terms = {
        term
        for member_id in or_groups[0].member_ids
        for term in _by_id(result, member_id).canonical_terms
    }
    assert member_terms == {"python", "java"}


def test_and_clause_creates_and_group():
    result = extract_deterministic(
        _requirements("Python and Django experience required.")
    )
    and_groups = [g for g in result.relationships if g.relationship == "AND"]
    assert len(and_groups) == 1
    member_terms = {
        term
        for member_id in and_groups[0].member_ids
        for term in _by_id(result, member_id).canonical_terms
    }
    assert member_terms == {"python", "django"}


def test_min_count_clause_creates_min_count_group():
    result = extract_deterministic(
        _requirements(
            "Proficiency in at least 2 of the following: Python, Java, Go."
        )
    )
    min_count_groups = [g for g in result.relationships if g.relationship == "MIN_COUNT"]
    assert len(min_count_groups) == 1
    group = min_count_groups[0]
    assert group.minimum_count == 2
    assert len(group.member_ids) == 3

    for member_id in group.member_ids:
        item = _by_id(result, member_id)
        assert item.ambiguous is True
        assert item.importance == "preferred"


def test_min_count_group_never_fabricates_members_below_threshold():
    """Only "Angular" resolves to a canonical skill here (Vue/React
    Native-style unknowns are not in the vocabulary) — with fewer than 2
    real members, no MIN_COUNT group is fabricated."""
    result = extract_deterministic(
        _requirements(
            "Proficiency in at least 2 of the following: Angular, Svelte, Ember."
        )
    )
    assert [g for g in result.relationships if g.relationship == "MIN_COUNT"] == []


def test_min_count_clause_never_double_counted_as_plain_requirement():
    result = extract_deterministic(
        _requirements(
            "Proficiency in at least 2 of the following: Python, Java, Go. "
        )
    )
    python_items = [
        item
        for item in result.requirements
        if item.requirement_type == "skill" and "python" in item.canonical_terms
    ]
    assert len(python_items) == 1
    assert python_items[0].ambiguous is True


def test_equivalent_clause_creates_equivalent_group_and_notes_alternative():
    result = extract_deterministic(
        _requirements("Bachelor's degree in Computer Science or equivalent experience.")
    )
    equivalent_groups = [g for g in result.relationships if g.relationship == "EQUIVALENT"]
    assert len(equivalent_groups) == 1

    education_item = next(
        item for item in result.requirements if item.requirement_type == "education"
    )
    assert education_item.equivalent_alternatives
    assert "equivalent" in education_item.equivalent_alternatives[0].lower()


def test_mixed_and_or_connectors_are_marked_ambiguous_not_grouped():
    result = extract_deterministic(
        _requirements("Python and Java or Go experience required.")
    )
    assert [g for g in result.relationships if g.relationship in ("AND", "OR")] == []
    for term in ("python", "java", "go"):
        assert _skills(result)[term].ambiguous is True


# ---------------------------------------------------------------------------
# Experience constraints
# ---------------------------------------------------------------------------

def test_at_least_years_experience():
    result = extract_deterministic(_requirements("5+ years of Python experience required."))
    exp = next(i for i in result.requirements if i.requirement_type == "experience")
    assert exp.experience.operator == "at_least"
    assert exp.experience.minimum_years == 5.0
    assert exp.experience.area == "python"


def test_range_years_experience():
    result = extract_deterministic(_requirements("3-5 years of Java experience required."))
    exp = next(i for i in result.requirements if i.requirement_type == "experience")
    assert exp.experience.operator == "range"
    assert exp.experience.minimum_years == 3.0
    assert exp.experience.maximum_years == 5.0


def test_up_to_years_experience():
    result = extract_deterministic(_requirements("Up to 2 years of Go experience preferred."))
    exp = next(i for i in result.requirements if i.requirement_type == "experience")
    assert exp.experience.operator == "at_most"
    assert exp.experience.maximum_years == 2.0


def test_experience_never_invented_from_unrelated_numbers():
    result = extract_deterministic(
        _requirements("Founded in 2015, our team of 12 engineers ships fast.")
    )
    assert [i for i in result.requirements if i.requirement_type == "experience"] == []


# ---------------------------------------------------------------------------
# Education / certifications
# ---------------------------------------------------------------------------

def test_education_requirement_with_field_of_study():
    result = extract_deterministic(
        _requirements("BS in Computer Science required.")
    )
    edu = next(i for i in result.requirements if i.requirement_type == "education")
    assert edu.education.degree_level == "Bachelor's"
    assert edu.education.field_of_study == "Computer Science"
    assert edu.importance == "required"


def test_certification_requirement():
    result = extract_deterministic(
        _requirements("AWS Certified Solutions Architect certification preferred.")
    )
    cert = next(i for i in result.requirements if i.requirement_type == "certification")
    assert cert.importance == "preferred"
    assert cert.certification.name


# ---------------------------------------------------------------------------
# Responsibilities vs. requirements
# ---------------------------------------------------------------------------

def test_responsibilities_never_become_scored_requirements():
    raw = RawRequirementSource(
        title="Engineer",
        requirements="Python required.",
        responsibilities="- Build and maintain APIs\n- Mentor junior engineers",
    )
    result = extract_deterministic(raw)
    responsibilities = [
        i for i in result.requirements if i.requirement_type == "responsibility"
    ]
    assert len(responsibilities) == 2
    for item in responsibilities:
        assert item.importance == "informational"
        assert item.hard_requirement is False


def test_responsibilities_text_excluded_from_requirement_scan():
    raw = RawRequirementSource(
        title="Engineer",
        requirements="Team overview.",
        responsibilities="5+ years of Python experience required.",
    )
    result = extract_deterministic(raw)
    assert [i for i in result.requirements if i.requirement_type == "experience"] == []


# ---------------------------------------------------------------------------
# Title / seniority
# ---------------------------------------------------------------------------

def test_seniority_extracted_from_title():
    result = extract_deterministic(
        RawRequirementSource(title="Senior Backend Engineer", requirements="Python required.")
    )
    assert result.seniority == "Senior"


def test_seniority_never_inferred_when_absent_from_title():
    result = extract_deterministic(
        RawRequirementSource(title="Backend Engineer", requirements="Python required.")
    )
    assert result.seniority is None


# ---------------------------------------------------------------------------
# Screening constraints kept separate from requirements
# ---------------------------------------------------------------------------

def test_background_check_is_a_screening_constraint_not_a_requirement():
    result = extract_deterministic(
        _requirements("Python required. A background check is required for this role.")
    )
    assert any(
        c.constraint_type == "background_check" and c.status == "required"
        for c in result.screening_constraints
    )
    assert all(
        "background" not in item.statement.lower() for item in result.requirements
    )


def test_drug_screening_and_drivers_license_constraints():
    result = extract_deterministic(
        _requirements(
            "Must pass a drug screening. A valid driver's license is required."
        )
    )
    types = {c.constraint_type for c in result.screening_constraints}
    assert "drug_screening" in types
    assert "drivers_license" in types


def test_citizenship_and_clearance_preferred_are_not_required():
    result = extract_deterministic(
        _requirements(
            "US citizenship preferred. Security clearance is a plus."
        )
    )
    by_type = {c.constraint_type: c.status for c in result.screening_constraints}
    assert by_type["citizenship"] == "preferred"
    assert by_type["security_clearance"] == "preferred"


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def test_duplicate_skill_mentions_are_merged_and_flagged():
    result = extract_deterministic(
        _requirements("Python required. Python is also a plus.")
    )
    python_items = [
        i for i in result.requirements if i.requirement_type == "skill" and "python" in i.canonical_terms
    ]
    assert len(python_items) == 1
    assert python_items[0].importance == "required"

    dup = next(d for d in result.duplicate_groups if d.canonical_key == "skill|python")
    assert len(dup.member_ids) == 2


def test_distinct_skills_are_not_flagged_as_duplicates():
    result = extract_deterministic(_requirements("Python required. Java required."))
    assert result.duplicate_groups == []


# ---------------------------------------------------------------------------
# Contradiction diagnostics
# ---------------------------------------------------------------------------

def test_conflicting_importance_contradiction():
    result = extract_deterministic(
        _requirements("Python required. Elsewhere, Python is nice to have.")
    )
    contradiction = next(
        c for c in result.contradictions if c.contradiction_type == "conflicting_importance"
    )
    assert len(contradiction.member_ids) == 2


def test_conflicting_experience_range_contradiction():
    result = extract_deterministic(
        _requirements(
            "5+ years of Python experience required. "
            "2 years of Python experience preferred."
        )
    )
    contradiction = next(
        c
        for c in result.contradictions
        if c.contradiction_type == "conflicting_experience_range"
    )
    assert "python" in contradiction.description.lower()


def test_conflicting_requirement_and_exclusion_contradiction():
    result = extract_deterministic(
        _requirements("No Rust experience is required. Rust experience is required.")
    )
    contradiction = next(
        c
        for c in result.contradictions
        if c.contradiction_type == "conflicting_requirement_and_exclusion"
    )
    assert len(contradiction.member_ids) == 2

    # The positive requirement still wins and is the one surfaced.
    rust_items = [
        i for i in result.requirements if i.requirement_type == "skill" and "rust" in i.canonical_terms
    ]
    assert len(rust_items) == 1
    assert rust_items[0].importance == "required"


def test_no_contradiction_for_a_single_clean_mention():
    result = extract_deterministic(_requirements("Python required."))
    assert result.contradictions == []


# ---------------------------------------------------------------------------
# Ambiguity
# ---------------------------------------------------------------------------

def test_ambiguous_requirement_ids_populated():
    result = extract_deterministic(
        _requirements(
            "Proficiency in at least 2 of the following: Python, Java, Go."
        )
    )
    ambiguous_ids = {item.id for item in result.requirements if item.ambiguous}
    assert ambiguous_ids == set(result.ambiguous_requirement_ids)
    assert len(ambiguous_ids) == 3


# ---------------------------------------------------------------------------
# Terminology normalization / related-but-different technology protection
# ---------------------------------------------------------------------------

def test_react_native_is_never_counted_as_plain_react():
    assert find_protected_skills("3+ years of React Native experience required.") == []


def test_plain_react_is_still_detected():
    assert find_protected_skills("3+ years of React experience required.") == ["react"]


def test_react_alongside_react_native_still_credits_react():
    skills = find_protected_skills(
        "Experience with both React and React Native is required."
    )
    assert "react" in skills


def test_react_native_end_to_end_extraction_does_not_fabricate_react_requirement():
    result = extract_deterministic(
        _requirements("3+ years of React Native experience required.")
    )
    assert "react" not in _skills(result)


def test_java_and_javascript_remain_distinct():
    skills = find_protected_skills("Experience with Java and JavaScript required.")
    assert "java" in skills
    assert "javascript" in skills


def test_node_red_is_never_counted_as_nodejs():
    assert find_protected_skills("Node-RED flow experience is a plus.") == []
