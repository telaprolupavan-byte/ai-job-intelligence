"""AJI-031: metric primitives and evidence grounding."""

from services.ai_evaluation.grounding import is_grounded, span_grounded
from services.ai_evaluation.metrics import SetTally, Tally, count, ratio


def test_ratio_carries_numerator_and_denominator():
    assert ratio(3, 4) == {"value": 0.75, "numerator": 3, "denominator": 4, "direction": "higher"}


def test_ratio_with_nothing_to_measure_is_none_not_zero():
    assert ratio(0, 0)["value"] is None


def test_count_defaults_to_lower_is_better():
    assert count(2) == {"value": 2, "direction": "lower"}


def test_set_tally_micro_averages_across_cases():
    tally = SetTally()

    fp, fn = tally.add({"python", "sql"}, {"python", "go"}, label="R1")
    tally.add({"java"}, {"java"}, label="R2")

    assert fp == {"go"} and fn == {"sql"}
    assert (tally.tp, tally.fp, tally.fn) == (2, 1, 1)
    assert tally.precision()["value"] == round(2 / 3, 4)
    assert tally.recall()["value"] == round(2 / 3, 4)
    assert tally.f1()["value"] == round(2 / 3, 4)
    assert tally.false_positive_items == ["R1: go"]
    assert tally.false_negative_items == ["R1: sql"]


def test_set_tally_f1_is_zero_when_nothing_is_right_and_none_when_undefined():
    wrong = SetTally()
    wrong.add({"a"}, {"b"})
    assert wrong.f1()["value"] == 0.0

    empty = SetTally()
    empty.add(set(), set())
    assert empty.precision()["value"] is None
    assert empty.f1()["value"] is None


def test_set_tally_metrics_prefixes_names():
    tally = SetTally()
    tally.add({"a"}, {"a"})

    assert set(tally.metrics("skill")) == {"skill_precision", "skill_recall", "skill_f1"}


def test_tally_accuracy():
    tally = Tally()
    assert tally.add(True) is True
    assert tally.add(False) is False

    assert tally.metric()["value"] == 0.5


def test_grounding_reuses_production_substring_rule():
    source = "Hands-on experience with\n  PyTorch or TensorFlow"

    assert is_grounded("experience with pytorch or TENSORFLOW", source)
    assert not is_grounded("experience with JAX", source)
    assert not is_grounded(None, source)
    assert not is_grounded("   ", source)


def test_span_grounding_requires_exact_offsets():
    source = "Strong Python skills"

    assert span_grounded("Python", 7, 13, source)
    assert not span_grounded("Python", 6, 12, source)
    assert not span_grounded("Python", 7, 100, source)
