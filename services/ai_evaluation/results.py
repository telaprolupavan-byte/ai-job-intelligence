"""Result containers shared by every AJI-031 capability evaluator.

A capability result is plain data (JSON-serializable via `to_dict`):
capability-specific metrics, per-case outcomes, and categorized
findings. Findings are categorized so that unsupported claims,
ordinary extraction errors, matching errors, requirement-interpretation
errors, grounding failures and prompt-injection findings are always
reported separately instead of being folded into one number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


FindingCategory = Literal[
    # The system asserted something the source text does not support.
    "unsupported_claim",
    # The system missed or misread something the source text states.
    "extraction_error",
    # Job Match / Gap Analysis reported a wrong match or gap.
    "matching_error",
    # Required/preferred tiers or AND/OR relationships were misread.
    "requirement_interpretation_error",
    # Claimed evidence is not present in the source text.
    "grounding_failure",
    # Instruction-like content in a resume or JD changed the output.
    "prompt_injection",
    # Not scored automatically: a person should look at it.
    "human_review",
    # The pipeline raised instead of returning a result.
    "error",
]

# Findings that make a case count as failed. `human_review` does not.
FAILING_CATEGORIES = frozenset(
    {
        "unsupported_claim",
        "extraction_error",
        "matching_error",
        "requirement_interpretation_error",
        "grounding_failure",
        "prompt_injection",
        "error",
    }
)


@dataclass
class Finding:
    category: FindingCategory
    case_id: str
    detail: str

    def to_dict(self) -> dict:
        return {"category": self.category, "case_id": self.case_id, "detail": self.detail}


@dataclass
class CapabilityResult:
    capability: str
    title: str
    mode: Literal["deterministic", "live"]
    stage: str
    metrics: dict[str, dict] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    case_ids: list[str] = field(default_factory=list)
    errored_case_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def add_case(self, case_id: str) -> None:
        if case_id not in self.case_ids:
            self.case_ids.append(case_id)

    def find(self, category: FindingCategory, case_id: str, detail: str) -> None:
        self.findings.append(Finding(category, case_id, detail))

    def error(self, case_id: str, exc: BaseException) -> None:
        self.add_case(case_id)
        self.errored_case_ids.append(case_id)
        self.find("error", case_id, f"{type(exc).__name__}: {exc}")

    def case_outcomes(self) -> list[dict]:
        outcomes = []

        for case_id in self.case_ids:
            failures = [
                finding.detail
                for finding in self.findings
                if finding.case_id == case_id
                and finding.category in FAILING_CATEGORIES
            ]
            outcomes.append(
                {"case_id": case_id, "passed": not failures, "failures": failures}
            )

        return outcomes

    def to_dict(self) -> dict:
        outcomes = self.case_outcomes()
        category_counts: dict[str, int] = {}

        for finding in self.findings:
            category_counts[finding.category] = (
                category_counts.get(finding.category, 0) + 1
            )

        evaluated = len(self.case_ids)

        return {
            "capability": self.capability,
            "title": self.title,
            "mode": self.mode,
            "stage": self.stage,
            "cases_evaluated": evaluated,
            "cases_passed": sum(1 for item in outcomes if item["passed"]),
            "cases_errored": len(self.errored_case_ids),
            "error_rate": (
                round(len(self.errored_case_ids) / evaluated, 4) if evaluated else None
            ),
            "metrics": self.metrics,
            "finding_counts": dict(sorted(category_counts.items())),
            "findings": [finding.to_dict() for finding in self.findings],
            "cases": outcomes,
            "notes": self.notes,
            **({"extra": self.extra} if self.extra else {}),
        }
