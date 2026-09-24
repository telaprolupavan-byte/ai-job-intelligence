"""AJI-027: the AI may only add grounded explanation/guidance text."""

from apps.api.services.general_resume.service import (
    compute_deterministic_assessment,
)
from apps.api.services.general_resume.validator import (
    ai_request_items,
    merge_ai_explanations,
)

from tests.general_resume_fixtures import WEAK_BULLET_1, WEAK_RESUME


def _improvements():
    return compute_deterministic_assessment(WEAK_RESUME)[1]


def _bullet(improvements):
    return next(i for i in improvements if i.anchor_line == WEAK_BULLET_1)


def _ai(item_id, **fields):
    base = {
        "improvement_id": item_id,
        "explanation": "Responsibility phrasing hides what you did.",
        "explanation_evidence": "Responsible for the data quality checks",
        "guidance": "Lead with your action and, only if accurate, add a result.",
    }
    base.update(fields)
    return {"items": [base]}


def test_valid_grounded_ai_text_is_accepted():
    improvements = _improvements()
    bullet = _bullet(improvements)
    merged = merge_ai_explanations(improvements, _ai(bullet.improvement_id))
    result = _bullet(merged)

    assert result.explanation_source == "ai"
    assert result.guidance_source == "ai"


def test_ungrounded_quote_falls_back_to_templates():
    improvements = _improvements()
    bullet = _bullet(improvements)
    merged = merge_ai_explanations(
        improvements,
        _ai(bullet.improvement_id, explanation_evidence="Led a team of 12"),
    )
    result = _bullet(merged)

    assert result.explanation == bullet.explanation
    assert result.explanation_source == "deterministic"
    assert result.guidance_source == "deterministic"


def test_quote_from_elsewhere_in_resume_is_not_grounding():
    """Grounding is scoped to the improvement's own evidence line."""
    improvements = _improvements()
    bullet = _bullet(improvements)
    merged = merge_ai_explanations(
        improvements,
        _ai(bullet.improvement_id, explanation_evidence="fraud detection pipeline"),
    )

    assert _bullet(merged).explanation_source == "deterministic"


def test_invented_numbers_are_rejected():
    improvements = _improvements()
    bullet = _bullet(improvements)
    merged = merge_ai_explanations(
        improvements,
        _ai(
            bullet.improvement_id,
            explanation="This could show a 30% gain.",
            guidance="Only if accurate, say it reduced errors by 40%.",
        ),
    )
    result = _bullet(merged)

    assert result.explanation_source == "deterministic"
    assert result.guidance_source == "deterministic"


def test_drafted_resume_text_in_guidance_is_rejected():
    improvements = _improvements()
    bullet = _bullet(improvements)
    merged = merge_ai_explanations(
        improvements,
        _ai(
            bullet.improvement_id,
            guidance='Only if accurate, try "Owned data quality checks end to end".',
        ),
    )

    assert _bullet(merged).guidance_source == "deterministic"


def test_add_if_true_guidance_must_be_conditional():
    improvements = _improvements()
    bullet = _bullet(improvements)
    assert bullet.suggestion_type == "ADD_IF_TRUE"
    merged = merge_ai_explanations(
        improvements,
        _ai(bullet.improvement_id, guidance="Add the result you achieved."),
    )

    assert _bullet(merged).guidance_source == "deterministic"


def test_ai_cannot_change_structure_or_add_items():
    improvements = _improvements()
    bullet = _bullet(improvements)
    ai = _ai(bullet.improvement_id, suggestion_type="REPHRASE_EXISTING", kind="x")
    ai["items"].append({
        "improvement_id": "invented",
        "explanation": "x",
        "explanation_evidence": "x",
        "guidance": "x",
    })
    merged = merge_ai_explanations(improvements, ai)

    assert [i.improvement_id for i in merged] == [
        i.improvement_id for i in improvements
    ]
    for before, after in zip(improvements, merged):
        assert before.model_dump(
            exclude={"explanation", "explanation_source", "guidance", "guidance_source"}
        ) == after.model_dump(
            exclude={"explanation", "explanation_source", "guidance", "guidance_source"}
        )


def test_malformed_ai_output_never_raises():
    improvements = _improvements()

    for bad in ({}, {"items": None}, {"items": ["x", 3, {"improvement_id": 5}]}):
        assert merge_ai_explanations(improvements, bad) == improvements


def test_only_evidence_lines_are_sent_to_the_ai():
    text = WEAK_RESUME.replace("jane@example.com | ", "")
    improvements = compute_deterministic_assessment(text)[1]
    items = ai_request_items(improvements)

    assert all(item["evidence"] for item in items)
    assert "missing_contact" not in {item["kind"] for item in items}
    assert all(set(item) == {
        "improvement_id", "kind", "suggestion_type", "issues", "evidence",
    } for item in items)
