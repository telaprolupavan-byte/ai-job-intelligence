"""Transparent metric primitives for AJI-031.

Every metric is a small JSON-serializable dict that carries its own
numerator and denominator, so a reader of a report can recompute it by
hand. `direction` records whether a higher or a lower value is better;
the regression comparison (`report.compare_reports`) uses it.

A metric with nothing to measure has `value: None` rather than a made-up
0 or 1 (for example, precision when the system produced no items).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal


Direction = Literal["higher", "lower"]


def ratio(numerator: int, denominator: int, *, direction: Direction = "higher") -> dict:
    return {
        "value": round(numerator / denominator, 4) if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
        "direction": direction,
    }


def count(value: int, *, direction: Direction = "lower") -> dict:
    return {"value": value, "direction": direction}


@dataclass
class SetTally:
    """Accumulates true/false positives and false negatives for a set
    comparison across cases (micro-averaged)."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    false_positive_items: list[str] = field(default_factory=list)
    false_negative_items: list[str] = field(default_factory=list)

    def add(
        self,
        expected: Iterable[str],
        actual: Iterable[str],
        *,
        label: str = "",
    ) -> tuple[set[str], set[str]]:
        """Add one case. Returns the (false positives, false negatives)."""
        expected_set = set(expected)
        actual_set = set(actual)
        false_positives = actual_set - expected_set
        false_negatives = expected_set - actual_set

        self.tp += len(actual_set & expected_set)
        self.fp += len(false_positives)
        self.fn += len(false_negatives)

        prefix = f"{label}: " if label else ""
        self.false_positive_items.extend(
            f"{prefix}{item}" for item in sorted(false_positives)
        )
        self.false_negative_items.extend(
            f"{prefix}{item}" for item in sorted(false_negatives)
        )

        return false_positives, false_negatives

    def precision(self) -> dict:
        return ratio(self.tp, self.tp + self.fp)

    def recall(self) -> dict:
        return ratio(self.tp, self.tp + self.fn)

    def f1(self) -> dict:
        precision = self.precision()["value"]
        recall = self.recall()["value"]

        if precision is None or recall is None or precision + recall == 0:
            value = None if precision is None or recall is None else 0.0
        else:
            value = round(2 * precision * recall / (precision + recall), 4)

        return {"value": value, "direction": "higher"}

    def metrics(self, prefix: str) -> dict[str, dict]:
        return {
            f"{prefix}_precision": self.precision(),
            f"{prefix}_recall": self.recall(),
            f"{prefix}_f1": self.f1(),
        }


@dataclass
class Tally:
    """Counts correct outcomes out of a total (accuracy / rate)."""

    correct: int = 0
    total: int = 0

    def add(self, ok: bool) -> bool:
        self.total += 1
        self.correct += int(ok)
        return ok

    def metric(self, *, direction: Direction = "higher") -> dict:
        return ratio(self.correct, self.total, direction=direction)
