"""Unit tests for the Resume Improvement (AJI-021) deterministic core.

No database, no FastAPI, no AI provider. This is the suite that pins the
ticket's safety rules, so each test names the rule it protects.
"""

import pytest

from apps.api.services.resume_ai.deterministic import (
    SECTION_ALIASES,
    analyze_resume_deterministically,
    normalize_heading,
)
from apps.api.services.resume_improvement.engine import (
    IMPROVEMENT_SECTION_HEADING,
    GapReference,
    ImprovementValidationError,
    ValidatedDecision,
    build_comparison,
    build_improved_content,
    build_transitions,
    compute_approval_fingerprint,
    next_improvement_version_name,
    sanitize_user_content,
    validate_decisions,
)


PARENT_RESUME = """Jane Doe
jane@example.com

PROFESSIONAL EXPERIENCE
- Built payment services in Python at Acme.

SKILLS
Python, SQL
"""


def _gap(
    requirement_id: str = "req-1",
    *,
    suggestion_type: str = "ADD_IF_TRUE",
    requirement_text: str = "Kubernetes",
    category: str = "must_have",
) -> GapReference:
    return GapReference(
        requirement_id=requirement_id,
        requirement_text=requirement_text,
        category=category,
        suggestion_type=suggestion_type,
    )


def _gaps(*references: GapReference) -> dict[str, GapReference]:
    return {reference.requirement_id: reference for reference in references}


def _approved(
    requirement_id: str = "req-1",
    *,
    applied_text: str = "Ran Kubernetes clusters in production for two years.",
    suggestion_type: str = "ADD_IF_TRUE",
    truth_confirmed: bool = True,
) -> ValidatedDecision:
    return ValidatedDecision(
        requirement_id=requirement_id,
        requirement_text="Kubernetes",
        category="must_have",
        suggestion_type=suggestion_type,
        action="approve",
        truth_confirmed=truth_confirmed,
        applied_text=applied_text,
    )


# ---------------------------------------------------------------------------
# Rule: user approval is mandatory
# ---------------------------------------------------------------------------

def test_a_submission_with_no_approvals_is_rejected():
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[{"requirement_id": "req-1", "action": "skip"}],
            gaps_by_requirement_id=_gaps(_gap()),
        )

    assert exc.value.code == "no_approvals"


def test_skipping_every_suggestion_never_produces_content():
    # Even reaching the builder with only skips leaves the resume alone.
    assert (
        build_improved_content(
            parent_content=PARENT_RESUME,
            decisions=[
                ValidatedDecision(
                    requirement_id="req-1",
                    requirement_text="Kubernetes",
                    category="must_have",
                    suggestion_type="ADD_IF_TRUE",
                    action="skip",
                    truth_confirmed=False,
                    applied_text=None,
                )
            ],
        )
        == PARENT_RESUME
    )


# ---------------------------------------------------------------------------
# Rule: ADD_IF_TRUE requires explicit truth confirmation
# ---------------------------------------------------------------------------

def test_approving_add_if_true_without_confirmation_is_rejected():
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[
                {
                    "requirement_id": "req-1",
                    "action": "approve",
                    "user_content": "I have run Kubernetes in production.",
                    "truth_confirmed": False,
                }
            ],
            gaps_by_requirement_id=_gaps(_gap()),
        )

    assert exc.value.code == "truth_confirmation_required"


def test_omitting_truth_confirmed_entirely_is_not_read_as_confirmation():
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[
                {
                    "requirement_id": "req-1",
                    "action": "approve",
                    "user_content": "I have run Kubernetes in production.",
                }
            ],
            gaps_by_requirement_id=_gaps(_gap()),
        )

    assert exc.value.code == "truth_confirmation_required"


def test_suggestion_type_is_taken_from_the_stored_gap_not_the_request():
    # The request cannot relabel an ADD_IF_TRUE gap to dodge the
    # confirmation: `validate_decisions` only ever reads the type from
    # `gaps_by_requirement_id`, and the input model forbids the field.
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[
                {
                    "requirement_id": "req-1",
                    "action": "approve",
                    "user_content": "Rephrased my existing AWS work.",
                    "truth_confirmed": False,
                    # A client attempting to pass a softer type.
                    "suggestion_type": "REPHRASE_EXISTING",
                }
            ],
            gaps_by_requirement_id=_gaps(_gap(suggestion_type="ADD_IF_TRUE")),
        )

    assert exc.value.code == "truth_confirmation_required"


def test_rephrase_existing_does_not_require_truth_confirmation():
    validated = validate_decisions(
        decisions=[
            {
                "requirement_id": "req-1",
                "action": "approve",
                "user_content": "Deployed and operated services on AWS.",
            }
        ],
        gaps_by_requirement_id=_gaps(
            _gap(suggestion_type="REPHRASE_EXISTING")
        ),
    )

    assert validated[0].action == "approve"
    assert validated[0].truth_confirmed is False


# ---------------------------------------------------------------------------
# Rule: never fabricate qualifications or evidence
# ---------------------------------------------------------------------------

def test_approving_without_user_content_is_rejected():
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[
                {
                    "requirement_id": "req-1",
                    "action": "approve",
                    "truth_confirmed": True,
                }
            ],
            gaps_by_requirement_id=_gaps(_gap()),
        )

    assert exc.value.code == "content_required"


def test_whitespace_only_content_is_not_accepted_as_approval_content():
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[
                {
                    "requirement_id": "req-1",
                    "action": "approve",
                    "truth_confirmed": True,
                    "user_content": "   \n\t  ",
                }
            ],
            gaps_by_requirement_id=_gaps(_gap()),
        )

    assert exc.value.code == "content_required"


def test_generated_content_contains_only_user_text_and_the_fixed_heading():
    content = build_improved_content(
        parent_content=PARENT_RESUME,
        decisions=[
            _approved(
                applied_text="Ran Kubernetes clusters in production for "
                "two years."
            )
        ],
    )

    added = content[len(PARENT_RESUME.rstrip()) :]

    # The requirement text, the JD evidence, and any suggestion string
    # are the three places an unverified claim could come from. None of
    # them reaches the resume.
    assert "Kubernetes clusters in production" in added
    assert added.strip().splitlines()[0] == IMPROVEMENT_SECTION_HEADING
    assert all(
        line == IMPROVEMENT_SECTION_HEADING or line.startswith("- ")
        for line in added.strip().splitlines()
    )


def test_the_parent_resume_text_survives_verbatim_inside_the_child():
    content = build_improved_content(
        parent_content=PARENT_RESUME,
        decisions=[_approved()],
    )

    assert content.startswith(PARENT_RESUME.rstrip())
    for line in PARENT_RESUME.strip().splitlines():
        assert line in content


def test_sanitize_strips_control_characters_without_rewriting_wording():
    assert (
        sanitize_user_content("Led\x00 the\x07 migration.")
        == "Led the migration."
    )
    assert (
        sanitize_user_content("  Led the migration.\r\n\r\n\r\n Twice. ")
        == "Led the migration.\nTwice."
    )


def test_a_multi_line_approval_becomes_multiple_bullets():
    content = build_improved_content(
        parent_content=PARENT_RESUME,
        decisions=[_approved(applied_text="First true line.\nSecond true line.")],
    )

    assert "- First true line." in content
    assert "- Second true line." in content


# ---------------------------------------------------------------------------
# Rule: the appended block must be scored as demonstrated experience
# ---------------------------------------------------------------------------

def test_the_block_heading_is_a_recognized_experience_section_alias():
    # If this ever stops being a recognized alias, appended content can
    # fall inside a trailing Skills section and be scored `skills_only`
    # (ATS `partial`) instead of demonstrated (`matched`). See the
    # engine module docstring.
    assert (
        normalize_heading(IMPROVEMENT_SECTION_HEADING)
        in SECTION_ALIASES["experience"]
    )


def test_appended_content_is_demonstrated_even_after_a_trailing_skills_section():
    content = build_improved_content(
        parent_content=PARENT_RESUME,
        decisions=[
            _approved(
                applied_text="Operated Kubernetes clusters serving "
                "production traffic."
            )
        ],
    )

    analysis = analyze_resume_deterministically(content)

    assert analysis.skill_evidence["kubernetes"]["demonstrated_mentions"] > 0


# ---------------------------------------------------------------------------
# Rule: prevent duplicate approval/version creation
# ---------------------------------------------------------------------------

def test_the_same_approvals_produce_the_same_fingerprint():
    first = compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-1",
        decisions=[_approved("req-1"), _approved("req-2")],
    )
    second = compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-1",
        decisions=[_approved("req-2"), _approved("req-1")],
    )

    assert first == second


def test_changing_the_approved_text_changes_the_fingerprint():
    first = compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-1",
        decisions=[_approved(applied_text="One true sentence.")],
    )
    second = compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-1",
        decisions=[_approved(applied_text="A different true sentence.")],
    )

    assert first != second


def test_toggling_an_unrelated_skip_does_not_change_the_fingerprint():
    skipped = ValidatedDecision(
        requirement_id="req-9",
        requirement_text="Terraform",
        category="preferred",
        suggestion_type="ADD_IF_TRUE",
        action="skip",
        truth_confirmed=False,
        applied_text=None,
    )

    without_skip = compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-1",
        decisions=[_approved()],
    )
    with_skip = compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-1",
        decisions=[_approved(), skipped],
    )

    assert without_skip == with_skip


def test_a_different_parent_version_produces_a_different_fingerprint():
    assert compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-1",
        decisions=[_approved()],
    ) != compute_approval_fingerprint(
        gap_analysis_id="gap-1",
        parent_resume_version_id="version-2",
        decisions=[_approved()],
    )


# ---------------------------------------------------------------------------
# Decision-set integrity
# ---------------------------------------------------------------------------

def test_a_requirement_absent_from_the_gap_analysis_is_rejected():
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[
                {
                    "requirement_id": "invented-requirement",
                    "action": "approve",
                    "truth_confirmed": True,
                    "user_content": "Anything at all.",
                }
            ],
            gaps_by_requirement_id=_gaps(_gap("req-1")),
        )

    assert exc.value.code == "unknown_requirement"


def test_deciding_the_same_requirement_twice_is_rejected():
    with pytest.raises(ImprovementValidationError) as exc:
        validate_decisions(
            decisions=[
                {
                    "requirement_id": "req-1",
                    "action": "approve",
                    "truth_confirmed": True,
                    "user_content": "First.",
                },
                {
                    "requirement_id": "req-1",
                    "action": "approve",
                    "truth_confirmed": True,
                    "user_content": "Second.",
                },
            ],
            gaps_by_requirement_id=_gaps(_gap("req-1")),
        )

    assert exc.value.code == "duplicate_decision"


def test_requirement_text_and_category_are_copied_from_the_stored_gap():
    validated = validate_decisions(
        decisions=[
            {
                "requirement_id": "req-1",
                "action": "approve",
                "truth_confirmed": True,
                "user_content": "True statement.",
            }
        ],
        gaps_by_requirement_id=_gaps(
            _gap(requirement_text="Production Kubernetes", category="preferred")
        ),
    )

    assert validated[0].requirement_text == "Production Kubernetes"
    assert validated[0].category == "preferred"
    assert validated[0].content_source == "user"


# ---------------------------------------------------------------------------
# Version naming
# ---------------------------------------------------------------------------

def test_improvement_versions_are_numbered_independently_of_uploads():
    assert next_improvement_version_name(["Original", "Version 2"]) == "Improved 1"
    assert (
        next_improvement_version_name(["Original", "Improved 1"]) == "Improved 2"
    )
    assert (
        next_improvement_version_name(["Improved 1", "Improved 3"]) == "Improved 2"
    )


# ---------------------------------------------------------------------------
# Comparison (arithmetic over two stored results only)
# ---------------------------------------------------------------------------

def _requirement(requirement_id: str, status: str, category="must_have") -> dict:
    return {
        "requirement_id": requirement_id,
        "requirement_text": f"Requirement {requirement_id}",
        "category": category,
        "status": status,
    }


def test_transitions_classify_improvement_regression_and_no_change():
    transitions = build_transitions(
        baseline_requirements=[
            _requirement("a", "missing"),
            _requirement("b", "matched"),
            _requirement("c", "partial"),
        ],
        recheck_requirements=[
            _requirement("a", "matched"),
            _requirement("b", "partial"),
            _requirement("c", "partial"),
        ],
        approved_requirement_ids={"a"},
    )

    by_id = {item["requirement_id"]: item for item in transitions}

    assert by_id["a"]["direction"] == "improved"
    assert by_id["a"]["was_approved"] is True
    assert by_id["b"]["direction"] == "regressed"
    assert by_id["c"]["direction"] == "unchanged"
    assert by_id["c"]["was_approved"] is False


def test_a_requirement_present_on_only_one_side_is_reported_not_dropped():
    transitions = build_transitions(
        baseline_requirements=[_requirement("gone", "partial")],
        recheck_requirements=[_requirement("new", "matched")],
        approved_requirement_ids=set(),
    )

    by_id = {item["requirement_id"]: item for item in transitions}

    assert by_id["gone"]["direction"] == "removed"
    assert by_id["gone"]["after_status"] is None
    assert by_id["new"]["direction"] == "added"
    assert by_id["new"]["before_status"] is None


def test_comparison_reports_a_score_drop_faithfully():
    comparison = build_comparison(
        baseline_id="ats-1",
        baseline_resume_version_id="version-1",
        baseline_score=70.0,
        baseline_result={
            "must_have_matched": 2,
            "must_have_total": 3,
            "preferred_matched": 1,
            "preferred_total": 2,
            "requirement_results": [_requirement("a", "matched")],
        },
        recheck_id="ats-2",
        recheck_resume_version_id="version-2",
        recheck_score=64.5,
        recheck_result={
            "must_have_matched": 1,
            "must_have_total": 3,
            "preferred_matched": 1,
            "preferred_total": 2,
            "requirement_results": [_requirement("a", "partial")],
        },
        approved_requirement_ids={"a"},
    )

    assert comparison["score_delta"] == -5.5
    assert comparison["must_have_delta"] == -1
    assert comparison["preferred_delta"] == 0
    assert comparison["regressed_count"] == 1
    assert comparison["improved_count"] == 0
