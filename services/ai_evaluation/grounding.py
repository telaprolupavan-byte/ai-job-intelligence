"""Evidence grounding checks for AJI-031.

NERO already decides whether an AI claim is grounded with one mechanism:
a case- and whitespace-insensitive substring match of the claimed
evidence against the source text
(`apps.api.services.job_intelligence.validator._evidence_supported`, also
used in the same form by the Requirement Intelligence and Gap Analysis
validators). The evaluation reuses that exact function instead of
defining a second, possibly stricter or looser, notion of "grounded", so
an evaluation verdict always agrees with what production would accept.

Requirement Intelligence additionally records character-offset
provenance (`SourceSpan`). `span_grounded` checks that native mechanism:
the span's text must be exactly the source text at those offsets.
"""

from __future__ import annotations

from apps.api.services.job_intelligence.validator import _evidence_supported


def is_grounded(evidence: str | None, source_text: str) -> bool:
    """True when `evidence` occurs in `source_text` under NERO's own
    production grounding rule."""
    return _evidence_supported(evidence, source_text)


def span_grounded(text: str, start: int, end: int, source_text: str) -> bool:
    """True when a Requirement Intelligence source span points at exactly
    `text` inside `source_text`."""
    return 0 <= start < end <= len(source_text) and source_text[start:end] == text
