"""AJI-027: the General Resume Score is deterministic, job-independent,
ratio-based, equally weighted, and has no bands or thresholds."""

import inspect

from apps.api.services.general_resume import scoring
from apps.api.services.general_resume.scoring import score_resume
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)

from tests.support.general_resume import STRONG_RESUME, WEAK_RESUME


def _score(text):
    return score_resume(analyze_resume_deterministically(text))


def _components(result):
    return {component.key: component for component in result.components}


def test_score_is_deterministic():
    first = _score(WEAK_RESUME)
    second = _score(WEAK_RESUME)

    assert first == second


def test_five_components_with_equal_weights():
    result = _score(WEAK_RESUME)
    components = _components(result)

    assert set(components) == {
        "structure",
        "action_writing",
        "measurable_impact",
        "clarity",
        "skill_evidence",
    }
    assert {c.weight for c in result.components} == {0.2}
    expected = sum(c.score for c in result.components) / 5

    assert result.overall_score == round(expected, 1)


def test_component_ratios_on_a_known_resume():
    components = _components(_score(WEAK_RESUME))

    assert components["structure"].score == 100.0
    assert (components["action_writing"].numerator, components["action_writing"].denominator) == (2, 4)
    assert (components["measurable_impact"].numerator, components["measurable_impact"].denominator) == (2, 4)
    assert (components["clarity"].numerator, components["clarity"].denominator) == (2, 4)
    # python, kubernetes, docker, machine learning, model serving;
    # only docker is skills-list-only.
    assert (components["skill_evidence"].numerator, components["skill_evidence"].denominator) == (4, 5)


def test_clarity_ignores_repeated_phrases():
    """PO decision: Clarity counts weak phrases only. Every bullet here
    repeats "for the", and none uses a weak phrase."""
    text = STRONG_RESUME.replace(
        "processing 2M events per day.",
        "for the risk team processing 2M events per day.",
    ).replace(
        "reducing latency by 35%.",
        "for the platform team, reducing latency by 35%.",
    )

    assert _components(_score(text))["clarity"].score == 100.0


def test_resume_length_neutrality():
    """Doubling the same content does not raise the score."""
    body = STRONG_RESUME.split("EDUCATION")[0]
    doubled = body + body.split("PROFESSIONAL EXPERIENCE")[1] + (
        "EDUCATION" + STRONG_RESUME.split("EDUCATION")[1]
    )

    assert _score(doubled).overall_score == _score(STRONG_RESUME).overall_score


def test_insufficient_data_components_are_excluded_not_zeroed():
    text = """Jane Doe
jane@example.com 555-123-4567

EXPERIENCE
Engineer at Acme building data systems for a long time with many people.

EDUCATION
B.S. Computer Science, State University

SKILLS
Underwater basket weaving, public speaking
"""
    result = _score(text)
    components = _components(result)

    for key in ("action_writing", "measurable_impact", "clarity", "skill_evidence"):
        assert components[key].status == "insufficient_data"
        assert components[key].score is None
        assert components[key].weight == 0.0

    # Only Structure was measurable, so it alone is the average.
    assert components["structure"].weight == 1.0
    assert result.overall_score == components["structure"].score


def test_score_takes_only_resume_analysis():
    """No job, requirement, preference or threshold input exists."""
    parameters = list(inspect.signature(score_resume).parameters)

    assert parameters == ["analysis"]


def test_no_band_or_threshold_in_scoring_module():
    source = inspect.getsource(scoring)

    for forbidden in ("THRESHOLD", "threshold =", "PASS", "band =", " 80"):
        assert forbidden not in source

    result = _score(WEAK_RESUME)
    dumped = str([c.model_dump() for c in result.components])

    for forbidden in ("pass", "fail", "strong", "weak_band", "grade"):
        assert f"'{forbidden}'" not in dumped
