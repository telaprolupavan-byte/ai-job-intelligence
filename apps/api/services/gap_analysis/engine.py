"""Gap Analysis (AJI-015) deterministic core.

DB-free, AI-free. This module never reimplements or re-derives ATS
scoring or requirement status: `select_gap_candidates()` only reads the
`status` / `jd_evidence` / `resume_evidence` fields an existing AJI-013
`AtsAlignmentResult.result["requirement_results"]` entry already carries,
verbatim, and filters to the ones that are not `matched`.

The one piece of new logic this module owns is `default_suggestion_type`
— the evidence-safety rule the AJI-015 spec requires ("missing candidate
evidence must produce an ADD_IF_TRUE-style recommendation rather than
fabricated resume content"). It is derived purely from `status`, not from
any AI judgment, so it holds even if the AI stage is unavailable or its
output is rejected by the validator:

- `missing` (services/ats_alignment/engine.py guarantees zero resume
  evidence for this status) -> `ADD_IF_TRUE`, a conditional prompt for
  the candidate to confirm before adding anything.
- `partial` (services/ats_alignment/engine.py guarantees *some* resume
  evidence exists for this status) -> `REPHRASE_EXISTING`, since there is
  always real resume evidence on hand to rephrase.

This module also provides the deterministic explanation/suggestion
templates used whenever the AI stage is unavailable or its output fails
the anti-hallucination check in `validator.py` — Gap Analysis must always
produce a safe, if less polished, result even with zero AI calls.
"""

from __future__ import annotations

from dataclasses import dataclass


GAP_STATUSES = ("missing", "partial")


@dataclass(frozen=True)
class GapCandidate:
    """One non-matched requirement, copied verbatim from an
    AtsAlignmentResult requirement result. Never re-evaluated."""

    requirement_id: str
    requirement_type: str
    category: str
    requirement_text: str
    status: str
    jd_evidence: str
    resume_evidence: str | None


def select_gap_candidates(requirement_results: list[dict]) -> list[GapCandidate]:
    """Select every ATS Alignment requirement result whose status is
    `missing` or `partial`. A `matched` requirement is not a gap and is
    excluded. Every field is copied as-is from the ATS result; nothing
    here re-decides a requirement's status."""
    candidates: list[GapCandidate] = []

    for item in requirement_results:
        if item["status"] not in GAP_STATUSES:
            continue

        candidates.append(
            GapCandidate(
                requirement_id=item["requirement_id"],
                requirement_type=item["requirement_type"],
                category=item["category"],
                requirement_text=item["requirement_text"],
                status=item["status"],
                jd_evidence=item["jd_evidence"],
                resume_evidence=item.get("resume_evidence"),
            )
        )

    return candidates


def default_suggestion_type(status: str) -> str:
    """The evidence-safety-critical status -> suggestion_type mapping.
    See module docstring. Never overridden for a `missing` requirement,
    regardless of what an AI stage proposes (see validator.py)."""
    if status == "missing":
        return "ADD_IF_TRUE"
    return "REPHRASE_EXISTING"


def deterministic_explanation(candidate: GapCandidate) -> str:
    """A safe, template-generated explanation used when no AI
    explanation is available or the AI's explanation fails evidence
    validation. Only ever restates data already present on the gap
    candidate — never asserts anything new about the candidate."""
    if candidate.status == "missing":
        return (
            f'The job requires "{candidate.requirement_text}" '
            f'(JD: "{candidate.jd_evidence}"), and no matching evidence '
            "was found in this resume version."
        )

    return (
        f'The job requires "{candidate.requirement_text}" '
        f'(JD: "{candidate.jd_evidence}"). The resume shows related but '
        f'incomplete evidence ("{candidate.resume_evidence}").'
    )


def deterministic_suggestion_text(
    candidate: GapCandidate, suggestion_type: str
) -> str:
    """A safe, template-generated suggestion used when no AI suggestion
    is available or the AI's suggestion fails validation. `ADD_IF_TRUE`
    phrasing is always conditional ("if you have...") — it never
    instructs the candidate to add something as if it were already
    verified true."""
    if suggestion_type == "ADD_IF_TRUE":
        return (
            f'If you have genuine experience with "{candidate.requirement_text}", '
            "consider adding it to your resume with specific, truthful "
            "details. Do not add this unless it is accurate."
        )

    if suggestion_type == "REPHRASE_EXISTING":
        return (
            f'Consider rephrasing or expanding on "{candidate.resume_evidence}" '
            f'to more clearly demonstrate "{candidate.requirement_text}", '
            "if accurate."
        )

    return (
        f'Consider highlighting "{candidate.resume_evidence}" more '
        f'prominently, since it relates to "{candidate.requirement_text}".'
    )
