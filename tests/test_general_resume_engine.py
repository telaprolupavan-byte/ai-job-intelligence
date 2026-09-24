"""AJI-027: applying a General Resume review. Pure engine, no DB."""

import pytest

from apps.api.services.general_resume.engine import (
    SECTION_HEADINGS,
    ReviewValidationError,
    build_refined_content,
    compute_review_fingerprint,
    next_refined_version_name,
    validate_review_decisions,
)
from apps.api.services.general_resume.service import (
    compute_deterministic_assessment,
)
from apps.api.services.resume_ai.deterministic import (
    SECTION_ALIASES,
    analyze_resume_deterministically,
    normalize_heading,
)

from tests.support.general_resume import (
    WEAK_BULLET_1,
    WEAK_BULLET_2,
    WEAK_RESUME,
)


def _improvements(text=WEAK_RESUME):
    return {i.improvement_id: i for i in compute_deterministic_assessment(text)[1]}


def _find(improvements, kind, **match):
    return next(
        i for i in improvements.values()
        if i.kind == kind and all(getattr(i, k) == v for k, v in match.items())
    )


def _validate(decisions, improvements=None):
    return validate_review_decisions(
        decisions=decisions,
        improvements_by_id=improvements or _improvements(),
    )


def test_section_headings_are_recognized_aliases():
    for section, heading in SECTION_HEADINGS.items():
        assert normalize_heading(heading) in SECTION_ALIASES[section]


def test_unknown_improvement_is_rejected():
    with pytest.raises(ReviewValidationError) as exc:
        _validate([{"improvement_id": "invented", "action": "reject"}])

    assert exc.value.code == "unknown_improvement"


def test_duplicate_decision_is_rejected():
    improvements = _improvements()
    target = next(iter(improvements))

    with pytest.raises(ReviewValidationError) as exc:
        _validate(
            [
                {"improvement_id": target, "action": "reject"},
                {"improvement_id": target, "action": "reject"},
            ],
            improvements,
        )

    assert exc.value.code == "duplicate_decision"


def test_approval_requires_user_content():
    improvements = _improvements()
    bullet = _find(improvements, "bullet", anchor_line=WEAK_BULLET_1)

    with pytest.raises(ReviewValidationError) as exc:
        _validate(
            [{"improvement_id": bullet.improvement_id, "action": "approve",
              "truth_confirmed": True, "user_content": "   "}],
            improvements,
        )

    assert exc.value.code == "content_required"


def test_add_if_true_requires_truth_confirmation():
    improvements = _improvements()
    bullet = _find(improvements, "bullet", anchor_line=WEAK_BULLET_1)
    assert bullet.suggestion_type == "ADD_IF_TRUE"

    with pytest.raises(ReviewValidationError) as exc:
        _validate(
            [{"improvement_id": bullet.improvement_id, "action": "approve",
              "user_content": "Owned data quality checks."}],
            improvements,
        )

    assert exc.value.code == "truth_confirmation_required"


def test_advisory_cannot_be_approved_but_can_be_rejected():
    text = WEAK_RESUME.replace("EDUCATION", "education")
    improvements = _improvements(text)
    advisory = _find(improvements, "inconsistent_headings")

    with pytest.raises(ReviewValidationError) as exc:
        _validate(
            [{"improvement_id": advisory.improvement_id, "action": "approve",
              "truth_confirmed": True, "user_content": "x"}],
            improvements,
        )
    assert exc.value.code == "advisory_not_applicable"

    validated = _validate(
        [{"improvement_id": advisory.improvement_id, "action": "reject"}],
        improvements,
    )
    assert validated[0].action == "reject"


def test_rejecting_everything_is_valid_and_changes_nothing():
    improvements = _improvements()
    validated = _validate(
        [{"improvement_id": i, "action": "reject"} for i in improvements],
        improvements,
    )

    assert all(d.action == "reject" and d.applied_text is None for d in validated)
    assert build_refined_content(
        parent_content=WEAK_RESUME, decisions=validated
    ) == WEAK_RESUME


def test_bullet_replacement_keeps_every_other_line_verbatim():
    improvements = _improvements()
    bullet = _find(improvements, "bullet", anchor_line=WEAK_BULLET_1)
    validated = _validate(
        [{"improvement_id": bullet.improvement_id, "action": "approve",
          "truth_confirmed": True,
          "user_content": "Owned data quality checks that cut bad rows by 40%."}],
        improvements,
    )

    refined = build_refined_content(parent_content=WEAK_RESUME, decisions=validated)

    assert WEAK_BULLET_1 not in refined
    assert "- Owned data quality checks that cut bad rows by 40%." in refined
    parent_lines = [l for l in WEAK_RESUME.split("\n") if l != WEAK_BULLET_1]
    refined_lines = refined.split("\n")
    for line in parent_lines:
        assert line in refined_lines
    assert WEAK_BULLET_2 in refined


def test_only_user_text_is_written():
    improvements = _improvements()
    bullet = _find(improvements, "bullet", anchor_line=WEAK_BULLET_1)
    validated = _validate(
        [{"improvement_id": bullet.improvement_id, "action": "approve",
          "truth_confirmed": True, "user_content": "My own words."}],
        improvements,
    )
    refined = build_refined_content(parent_content=WEAK_RESUME, decisions=validated)

    assert bullet.explanation not in refined
    assert bullet.guidance not in refined
    added = set(refined.split("\n")) - set(WEAK_RESUME.split("\n"))
    assert added == {"- My own words."}


def test_skill_is_appended_under_an_experience_heading_and_counts_as_demonstrated():
    improvements = _improvements()
    skill = _find(improvements, "skill_not_demonstrated", target="docker")
    validated = _validate(
        [{"improvement_id": skill.improvement_id, "action": "approve",
          "truth_confirmed": True,
          "user_content": "Packaged the fraud models with Docker."}],
        improvements,
    )
    refined = build_refined_content(parent_content=WEAK_RESUME, decisions=validated)

    assert refined.startswith(WEAK_RESUME.rstrip())
    assert refined.rstrip().endswith(
        "Professional Experience\n- Packaged the fraud models with Docker."
    )
    evidence = analyze_resume_deterministically(refined).skill_evidence
    assert evidence["docker"]["status"] == "demonstrated"


def test_missing_section_and_contact_placement():
    text = """Jane Doe

EXPERIENCE
- Built billing services at Acme serving 2M customers.
- Designed the ledger service used by 40 teams.
"""
    improvements = _improvements(text)
    email = _find(improvements, "missing_contact", target="email")
    education = _find(improvements, "missing_section", target="education")
    validated = _validate(
        [
            {"improvement_id": email.improvement_id, "action": "approve",
             "truth_confirmed": True, "user_content": "jane@example.com"},
            {"improvement_id": education.improvement_id, "action": "approve",
             "truth_confirmed": True, "user_content": "B.S. Computer Science"},
        ],
        improvements,
    )
    refined = build_refined_content(parent_content=text, decisions=validated)
    lines = refined.split("\n")

    assert lines[0] == "Jane Doe"
    assert lines[1] == "jane@example.com"
    assert refined.rstrip().endswith("Education\nB.S. Computer Science")
    analysis = analyze_resume_deterministically(refined)
    assert "education" in {s.name for s in analysis.sections}
    assert analysis.emails == ["jane@example.com"]


def test_stale_anchor_is_rejected():
    improvements = _improvements()
    bullet = _find(improvements, "bullet", anchor_line=WEAK_BULLET_1)
    validated = _validate(
        [{"improvement_id": bullet.improvement_id, "action": "approve",
          "truth_confirmed": True, "user_content": "x y z"}],
        improvements,
    )

    with pytest.raises(ReviewValidationError) as exc:
        build_refined_content(
            parent_content=WEAK_RESUME.replace(WEAK_BULLET_1, ""),
            decisions=validated,
        )

    assert exc.value.code == "stale_improvement"


def test_fingerprint_is_order_independent_and_includes_rejections():
    improvements = _improvements()
    ids = list(improvements)
    decisions = [{"improvement_id": i, "action": "reject"} for i in ids]

    first = compute_review_fingerprint(
        assessment_id="a", parent_resume_version_id="p",
        decisions=_validate(decisions, improvements),
    )
    reordered = compute_review_fingerprint(
        assessment_id="a", parent_resume_version_id="p",
        decisions=_validate(list(reversed(decisions)), improvements),
    )
    fewer = compute_review_fingerprint(
        assessment_id="a", parent_resume_version_id="p",
        decisions=_validate(decisions[1:], improvements),
    )

    assert first == reordered
    assert first != fewer


def test_refined_version_names():
    assert next_refined_version_name(["Original"]) == "Refined 1"
    assert next_refined_version_name(["Refined 1", "Improved 1"]) == "Refined 2"
    assert next_refined_version_name(["Refined 2"]) == "Refined 1"
