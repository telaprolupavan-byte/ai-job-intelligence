"""AJI-027: resume-level improvements are deterministic, stably
identified, grouped per bullet, and typed on the server."""

from apps.api.services.general_resume.improvements import (
    detect_improvements,
    improvement_id,
)
from apps.api.services.general_resume.service import (
    compute_deterministic_assessment,
)

from tests.general_resume_fixtures import (
    STRONG_RESUME,
    WEAK_BULLET_1,
    WEAK_RESUME,
)


def _improvements(text):
    return compute_deterministic_assessment(text)[1]


def test_strong_resume_has_no_improvements():
    assert _improvements(STRONG_RESUME) == []


def test_bullet_issues_are_grouped_into_one_improvement_per_line():
    bullets = [i for i in _improvements(WEAK_RESUME) if i.kind == "bullet"]

    assert len(bullets) == 2
    first = bullets[0]
    assert first.issues == ["weak_phrase", "no_action_verb", "no_quantification"]
    assert first.evidence == WEAK_BULLET_1[2:]
    assert first.anchor_line == WEAK_BULLET_1
    assert first.components == ["action_writing", "clarity", "measurable_impact"]


def test_suggestion_types_are_decided_deterministically():
    by_kind = {}
    for item in _improvements(WEAK_RESUME):
        by_kind.setdefault(item.kind, set()).add(item.suggestion_type)

    # Adding a measurable result is a new claim -> ADD_IF_TRUE.
    assert by_kind["bullet"] == {"ADD_IF_TRUE"}
    assert by_kind["skill_not_demonstrated"] == {"ADD_IF_TRUE"}


def test_rephrase_only_bullet_is_rephrase_existing():
    text = WEAK_RESUME.replace(
        WEAK_BULLET_1,
        "- Responsible for data quality checks that cut defects by 20%.",
    )
    bullet = next(
        i for i in _improvements(text)
        if i.kind == "bullet" and "cut defects" in (i.evidence or "")
    )

    assert "no_quantification" not in bullet.issues
    assert bullet.suggestion_type == "REPHRASE_EXISTING"


def test_ids_are_stable_for_unchanged_text_and_change_with_text():
    before = {i.improvement_id for i in _improvements(WEAK_RESUME)}
    changed = WEAK_RESUME.replace(
        WEAK_BULLET_1, "- Owned data quality checks for the feature store."
    )
    after = {i.improvement_id for i in _improvements(changed)}

    assert improvement_id("bullet", WEAK_BULLET_1) in before
    assert improvement_id("bullet", WEAK_BULLET_1) not in after
    # The untouched second weak bullet keeps its id.
    shared = before & after
    assert len(shared) == len(before) - 1


def test_missing_sections_and_contacts_are_add_if_true():
    text = """Jane Doe

EXPERIENCE
- Built billing services at Acme serving 2M customers.
- Designed the ledger service used by 40 teams.
"""
    items = _improvements(text)
    kinds = {(i.kind, i.target) for i in items}

    assert ("missing_contact", "email") in kinds
    assert ("missing_contact", "phone") in kinds
    assert ("missing_section", "education") in kinds
    assert ("missing_section", "skills") in kinds
    for item in items:
        if item.kind in ("missing_contact", "missing_section"):
            assert item.suggestion_type == "ADD_IF_TRUE"
            assert item.evidence is None


def test_insufficient_data_remains_visible_as_improvement_area():
    text = """Jane Doe
jane@example.com 555-123-4567

EXPERIENCE
Engineer at Acme building data systems for a long time with many people.

EDUCATION
B.S. Computer Science

SKILLS
Underwater basket weaving
"""
    items = {i.kind: i for i in _improvements(text)}

    assert items["no_bullets"].suggestion_type == "ADVISORY"
    assert set(items["no_bullets"].components) >= {
        "action_writing", "measurable_impact", "clarity",
    }
    assert items["no_recognized_skills"].suggestion_type == "ADVISORY"
    assert items["no_recognized_skills"].components == ["skill_evidence"]


def test_identical_bullets_share_one_improvement():
    text = WEAK_RESUME.replace(
        WEAK_BULLET_1 + "\n", WEAK_BULLET_1 + "\n" + WEAK_BULLET_1 + "\n"
    )
    ids = [i.improvement_id for i in _improvements(text)]

    assert len(ids) == len(set(ids))


def test_detect_improvements_signature_has_no_job_input():
    import inspect

    assert list(inspect.signature(detect_improvements).parameters) == [
        "text",
        "analysis",
        "insufficient_components",
    ]
