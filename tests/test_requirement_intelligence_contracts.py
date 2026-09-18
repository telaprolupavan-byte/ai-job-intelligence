import pytest
from pydantic import ValidationError

from apps.api.services.requirement_intelligence.contracts import (
    Contradiction,
    DomainTerminology,
    DuplicateGroup,
    QualityDiagnostics,
    RequirementGroup,
    RequirementIntelligenceResult,
    RequirementItem,
    ScreeningConstraint,
    SecurityDiagnostics,
    SourceSpan,
    TitleSeniorityInfo,
)


def _skill_item(**overrides) -> RequirementItem:
    defaults = dict(
        id="req-0001",
        requirement_type="skill",
        importance="required",
        statement="python (required)",
        canonical_terms=["python"],
        raw_text="Python required.",
    )
    defaults.update(overrides)
    return RequirementItem(**defaults)


def _result(**overrides) -> RequirementIntelligenceResult:
    defaults = dict(
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        source_id="job-1",
        identity=TitleSeniorityInfo(original_title="Software Engineer"),
    )
    defaults.update(overrides)
    return RequirementIntelligenceResult(**defaults)


# ---------------------------------------------------------------------------
# SourceSpan provenance
# ---------------------------------------------------------------------------

def test_source_span_accepts_consistent_bounds():
    span = SourceSpan(text="Python required", start=10, end=25)
    assert span.end - span.start == len(span.text)


def test_source_span_rejects_length_mismatch():
    with pytest.raises(ValidationError, match="length must match"):
        SourceSpan(text="Python required", start=10, end=20)


def test_source_span_rejects_end_before_start():
    with pytest.raises(ValidationError, match="end must be after start"):
        SourceSpan(text="x", start=5, end=5)


# ---------------------------------------------------------------------------
# RequirementItem consistency
# ---------------------------------------------------------------------------

def test_hard_requirement_must_be_importance_required():
    with pytest.raises(ValidationError, match="importance='required'"):
        _skill_item(importance="preferred", hard_requirement=True)


def test_hard_requirement_allowed_when_required():
    item = _skill_item(importance="required", hard_requirement=True)
    assert item.hard_requirement is True


def test_responsibility_can_never_be_required_or_preferred():
    with pytest.raises(ValidationError, match="responsibilities must never"):
        RequirementItem(
            id="req-0002",
            requirement_type="responsibility",
            importance="required",
            statement="Build APIs",
            raw_text="Build APIs",
        )


def test_responsibility_may_be_informational_or_contextual():
    item = RequirementItem(
        id="req-0002",
        requirement_type="responsibility",
        importance="informational",
        statement="Build APIs",
        raw_text="Build APIs",
    )
    assert item.importance == "informational"


def test_requirement_item_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RequirementItem(
            id="req-0001",
            requirement_type="skill",
            importance="required",
            statement="python",
            raw_text="Python required.",
            not_a_real_field="oops",
        )


# ---------------------------------------------------------------------------
# RequirementGroup relationships
# ---------------------------------------------------------------------------

def test_and_group_requires_at_least_two_members():
    with pytest.raises(ValidationError, match="at least 2"):
        RequirementGroup(
            id="grp-0001",
            relationship="AND",
            member_ids=["req-0001"],
            description="both",
            evidence_text="Python and Java",
        )


def test_or_group_with_two_members_is_valid():
    group = RequirementGroup(
        id="grp-0001",
        relationship="OR",
        member_ids=["req-0001", "req-0002"],
        description="either",
        evidence_text="Python or Java",
    )
    assert group.member_ids == ["req-0001", "req-0002"]


def test_equivalent_group_allows_single_member():
    group = RequirementGroup(
        id="grp-0001",
        relationship="EQUIVALENT",
        member_ids=["req-0001"],
        description="equivalent",
        evidence_text="AWS or equivalent",
    )
    assert group.member_ids == ["req-0001"]


def test_min_count_group_requires_positive_minimum_count():
    with pytest.raises(ValidationError, match="positive minimum_count"):
        RequirementGroup(
            id="grp-0001",
            relationship="MIN_COUNT",
            member_ids=["req-0001", "req-0002"],
            minimum_count=0,
            description="at least",
            evidence_text="at least 0 of",
        )


def test_min_count_group_rejects_minimum_exceeding_members():
    with pytest.raises(ValidationError, match="cannot exceed"):
        RequirementGroup(
            id="grp-0001",
            relationship="MIN_COUNT",
            member_ids=["req-0001", "req-0002"],
            minimum_count=3,
            description="at least 3",
            evidence_text="at least 3 of these 2",
        )


def test_minimum_count_only_applies_to_min_count_groups():
    with pytest.raises(ValidationError, match="only applies to MIN_COUNT"):
        RequirementGroup(
            id="grp-0001",
            relationship="OR",
            member_ids=["req-0001", "req-0002"],
            minimum_count=1,
            description="either",
            evidence_text="Python or Java",
        )


def test_group_rejects_repeated_member_ids():
    with pytest.raises(ValidationError, match="must not repeat"):
        RequirementGroup(
            id="grp-0001",
            relationship="OR",
            member_ids=["req-0001", "req-0001"],
            description="either",
            evidence_text="Python or Python",
        )


# ---------------------------------------------------------------------------
# Top-level referential integrity
# ---------------------------------------------------------------------------

def test_result_rejects_group_referencing_unknown_requirement():
    with pytest.raises(ValidationError, match="unknown requirement id"):
        _result(
            requirements=[_skill_item()],
            relationships=[
                RequirementGroup(
                    id="grp-0001",
                    relationship="OR",
                    member_ids=["req-0001", "req-9999"],
                    description="either",
                    evidence_text="Python or Rust",
                )
            ],
        )


def test_result_rejects_duplicate_requirement_ids():
    with pytest.raises(ValidationError, match="ids must be unique"):
        _result(requirements=[_skill_item(), _skill_item()])


def test_result_rejects_duplicate_group_ids():
    item_a = _skill_item(id="req-0001")
    item_b = _skill_item(id="req-0002", canonical_terms=["java"])
    group = RequirementGroup(
        id="grp-0001",
        relationship="OR",
        member_ids=["req-0001", "req-0002"],
        description="either",
        evidence_text="Python or Java",
    )
    with pytest.raises(ValidationError, match="group ids must be unique"):
        _result(
            requirements=[item_a, item_b],
            relationships=[group, group],
        )


def test_result_rejects_ambiguous_id_referencing_unknown_requirement():
    with pytest.raises(ValidationError, match="ambiguous_requirement_ids"):
        _result(
            requirements=[_skill_item()],
            quality=QualityDiagnostics(ambiguous_requirement_ids=["req-9999"]),
        )


def test_result_accepts_a_fully_consistent_snapshot():
    item_a = _skill_item(id="req-0001")
    item_b = _skill_item(id="req-0002", canonical_terms=["java"])
    result = _result(
        requirements=[item_a, item_b],
        relationships=[
            RequirementGroup(
                id="grp-0001",
                relationship="OR",
                member_ids=["req-0001", "req-0002"],
                description="either",
                evidence_text="Python or Java",
            )
        ],
        screening_constraints=[
            ScreeningConstraint(
                id="scr-0001",
                constraint_type="background_check",
                status="required",
                statement="A background check is required.",
                raw_text="Background check required.",
            )
        ],
        quality=QualityDiagnostics(
            duplicate_groups=[
                DuplicateGroup(
                    canonical_key="skill|python",
                    member_ids=["req-0001", "req-0002"],
                    note="kept req-0001",
                )
            ],
            contradictions=[
                Contradiction(
                    contradiction_type="conflicting_importance",
                    member_ids=["req-0001", "req-0002"],
                    description="conflict",
                )
            ],
            ambiguous_requirement_ids=["req-0001"],
        ),
        security=SecurityDiagnostics(prompt_injection_detected=False),
        domain=DomainTerminology(value="FinTech", confidence="medium"),
    )
    assert result.source_id == "job-1"
    assert len(result.requirements) == 2


# ---------------------------------------------------------------------------
# AJI-020A supervisor clarification pass — contract semantics proofs.
#
# These are documentation-proving tests, not new behavior: see the
# expanded docstrings on ImportanceTier/RequirementItem/RequirementGroup/
# ScreeningConstraint in contracts.py, and docs/ARCHITECTURE.md's
# "Contract semantics clarification" section, for the semantics being
# proven here.
# ---------------------------------------------------------------------------

def test_importance_and_hard_requirement_are_independently_representable():
    """`importance` and `hard_requirement` are distinct, orthogonal
    fields: a `required` item may or may not be `hard_requirement`."""
    soft_required = _skill_item(importance="required", hard_requirement=False)
    hard_required = _skill_item(importance="required", hard_requirement=True)

    assert soft_required.importance == "required"
    assert soft_required.hard_requirement is False
    assert hard_required.importance == "required"
    assert hard_required.hard_requirement is True


@pytest.mark.parametrize("importance", ["preferred", "contextual", "informational"])
def test_hard_requirement_impossible_on_any_non_required_tier(importance):
    with pytest.raises(ValidationError, match="importance='required'"):
        _skill_item(importance=importance, hard_requirement=True)


def test_screening_constraint_has_no_importance_or_hard_requirement_field():
    """`ScreeningConstraint` is a disjoint model type from
    `RequirementItem`: it carries its own `status`, never `importance`/
    `hard_requirement`."""
    field_names = set(ScreeningConstraint.model_fields.keys())
    assert "importance" not in field_names
    assert "hard_requirement" not in field_names
    assert "status" in field_names


def test_relationship_group_cannot_reference_a_screening_constraint_id():
    """Screening constraints never participate in AND/OR/MIN_COUNT/
    EQUIVALENT relationships — a group may only reference real
    `requirements` ids."""
    with pytest.raises(ValidationError, match="unknown requirement id"):
        _result(
            requirements=[_skill_item()],
            screening_constraints=[
                ScreeningConstraint(
                    id="scr-0001",
                    constraint_type="background_check",
                    status="required",
                    statement="A background check is required.",
                    raw_text="Background check required.",
                )
            ],
            relationships=[
                RequirementGroup(
                    id="grp-0001",
                    relationship="OR",
                    member_ids=["req-0001", "scr-0001"],
                    description="either",
                    evidence_text="Python or a background check",
                )
            ],
        )


def test_min_count_fulfillment_bounds_are_exact():
    """MIN_COUNT's explicit minimum/member semantics: minimum_count may
    equal the full member count (all are needed) but never exceed it,
    and must be at least 1."""
    exactly_all_required = RequirementGroup(
        id="grp-0001",
        relationship="MIN_COUNT",
        member_ids=["req-0001", "req-0002"],
        minimum_count=2,
        description="both of these two",
        evidence_text="at least 2 of these 2",
    )
    assert exactly_all_required.minimum_count == 2

    with pytest.raises(ValidationError, match="cannot exceed"):
        RequirementGroup(
            id="grp-0002",
            relationship="MIN_COUNT",
            member_ids=["req-0001", "req-0002"],
            minimum_count=3,
            description="more than available",
            evidence_text="at least 3 of these 2",
        )


def test_equivalent_group_member_must_be_a_real_requirement_not_ai_judgment():
    """An EQUIVALENT group still goes through the same referential-
    integrity check as every other relationship — it cannot reference a
    requirement that does not exist, which is what would happen if an
    AI-judged "these look similar" pairing tried to synthesize one."""
    with pytest.raises(ValidationError, match="unknown requirement id"):
        _result(
            requirements=[_skill_item()],
            relationships=[
                RequirementGroup(
                    id="grp-0001",
                    relationship="EQUIVALENT",
                    member_ids=["req-9999"],
                    description="fabricated equivalence",
                    evidence_text="AI-judged similarity",
                )
            ],
        )


def test_ai_decoding_schema_cannot_express_a_relationship():
    """The AI semantic-decoding stage's entire output schema is
    identity/domain fields only — it has no field capable of expressing
    an AND/OR/MIN_COUNT/EQUIVALENT relationship at all, so relationships
    (EQUIVALENT included) can never be an AI judgment call; they are
    produced exclusively by the deterministic extractor matching an
    explicit JD phrase."""
    from apps.api.services.requirement_intelligence.providers.openai_provider import (
        ProviderRequirementSemantics,
    )

    field_names = set(ProviderRequirementSemantics.model_fields.keys())
    forbidden_substrings = ("relationship", "equivalent", "group", "and_or", "min_count")

    for field_name in field_names:
        lowered = field_name.lower()
        assert not any(term in lowered for term in forbidden_substrings), field_name


def test_validator_ignores_relationship_like_keys_in_ai_semantics():
    """Even if an AI provider response somehow carried extra keys that
    look relationship-related, `build_requirement_intelligence_result`
    only ever reads `relationships` from deterministic extraction — the
    AI semantics dict is never consulted for it."""
    from apps.api.services.requirement_intelligence.deterministic import (
        DeterministicExtraction,
    )
    from apps.api.services.requirement_intelligence.validator import (
        build_requirement_intelligence_result,
    )

    deterministic = DeterministicExtraction(
        seniority=None,
        requirements=[_skill_item()],
        relationships=[],
        screening_constraints=[],
        duplicate_groups=[],
        contradictions=[],
        ambiguous_requirement_ids=[],
        security_signals=[],
    )

    result = build_requirement_intelligence_result(
        source_id="job-1",
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        model_provider="openai",
        model_name="test-model",
        extraction_status="complete",
        raw_title="Engineer",
        raw_text="Python required.",
        deterministic=deterministic,
        ai_semantics={
            "normalized_title": None,
            # A hypothetical malicious/malformed provider payload trying
            # to smuggle in a relationship-shaped key. It is simply
            # ignored: validator.py never reads anything but the fixed
            # identity/domain keys off ai_semantics.
            "relationships": [{"relationship": "EQUIVALENT", "member_ids": ["req-0001"]}],
        },
    )

    assert result.relationships == []
