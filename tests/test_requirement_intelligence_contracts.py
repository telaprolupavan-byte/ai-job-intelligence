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
