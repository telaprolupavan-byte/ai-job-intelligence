"""Merging optional AI explanations into deterministic improvements (AJI-027).

The AI may replace an improvement's `explanation` and `guidance` text,
and nothing else. Every other field - the id, kind, suggestion type,
components, evidence, and of course the score - is decided before the AI
is called and is copied through unchanged, whatever the AI returns. An
AI entry for an id that was not asked about is ignored.

An AI field is accepted only when all of these hold (otherwise that
field silently keeps its deterministic template - the same
silent-and-safe degrade Gap Analysis uses):

- **Grounding.** The improvement has evidence, and the AI's
  `explanation_evidence` is a verbatim (case/whitespace-insensitive)
  substring of *that improvement's own* evidence line - never of the
  whole resume. A failed grounding check drops both AI fields.
- **No invented numbers.** Neither field may contain a number that is
  not already in the evidence, so the AI cannot suggest a metric.
- **No drafted resume text.** `guidance` may not contain a
  double-quoted span: quoted text is how a suggested rewrite would be
  offered, and the AI must never author resume content.
- **Conditional `ADD_IF_TRUE` guidance.** Guidance for an `ADD_IF_TRUE`
  improvement must contain a hedge phrase ("if accurate", "if you
  have", ...), since it concerns a claim the resume does not make.
- **Bounded length.**
"""

from __future__ import annotations

import re
from typing import Any

from apps.api.services.general_resume.contracts import Improvement


MAX_AI_TEXT_LENGTH = 600

_HEDGE_PHRASES = (
    "if you have",
    "if you've",
    "if you actually",
    "if you did",
    "if you do",
    "if this is true",
    "if this is accurate",
    "if accurate",
    "if true",
    "if applicable",
    "if it is accurate",
    "if it's accurate",
    "only if",
)

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_QUOTED_SPAN = re.compile(r"[\"“”][^\"“”]{3,}[\"“”]")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _grounded(quote: Any, evidence: str | None) -> bool:
    if not evidence or not isinstance(quote, str):
        return False

    normalized = _normalize(quote)

    return bool(normalized) and normalized in _normalize(evidence)


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _acceptable_text(value: Any, evidence: str) -> bool:
    if not isinstance(value, str):
        return False

    text = value.strip()

    if not text or len(text) > MAX_AI_TEXT_LENGTH:
        return False

    return _numbers(text) <= _numbers(evidence)


def _hedged(text: str) -> bool:
    normalized = _normalize(text)
    return any(phrase in normalized for phrase in _HEDGE_PHRASES)


def merge_ai_explanations(
    improvements: list[Improvement],
    ai_result: dict[str, Any] | None,
) -> list[Improvement]:
    """Return the improvements with any AI text that passes every check.
    Never raises for a bad AI field."""
    if not ai_result:
        return improvements

    ai_by_id: dict[str, dict[str, Any]] = {}

    for item in ai_result.get("items") or []:
        if isinstance(item, dict) and isinstance(item.get("improvement_id"), str):
            ai_by_id.setdefault(item["improvement_id"], item)

    merged: list[Improvement] = []

    for improvement in improvements:
        item = ai_by_id.get(improvement.improvement_id)
        evidence = improvement.evidence

        if item is None or not _grounded(item.get("explanation_evidence"), evidence):
            merged.append(improvement)
            continue

        update: dict[str, Any] = {}
        explanation = item.get("explanation")
        guidance = item.get("guidance")

        if _acceptable_text(explanation, evidence):
            update["explanation"] = explanation.strip()
            update["explanation_source"] = "ai"

        if (
            _acceptable_text(guidance, evidence)
            and not _QUOTED_SPAN.search(guidance)
            and (
                improvement.suggestion_type != "ADD_IF_TRUE"
                or _hedged(guidance)
            )
        ):
            update["guidance"] = guidance.strip()
            update["guidance_source"] = "ai"

        merged.append(improvement.model_copy(update=update))

    return merged


def ai_request_items(improvements: list[Improvement]) -> list[dict[str, Any]]:
    """The only data sent to the AI: grounded improvements, each with its
    own evidence line. Improvements with no evidence (absences such as a
    missing section) keep their templates and are never sent."""
    return [
        {
            "improvement_id": improvement.improvement_id,
            "kind": improvement.kind,
            "suggestion_type": improvement.suggestion_type,
            "issues": list(improvement.issues),
            "evidence": improvement.evidence,
        }
        for improvement in improvements
        if improvement.evidence
    ]
