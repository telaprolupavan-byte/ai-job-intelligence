"""ATS Alignment overall-score aggregation (AJI-020).

Replaces AJI-013's explicitly-documented placeholder (every requirement
counted equally, `SCORING_VERSION = "placeholder-1.0"` — see git history
of this module) with the approved real formula: a deterministic
composite of four independently-scored, independently-explainable
dimensions, weighted per `services.ats_alignment.weights.SCORE_WEIGHTS`:

- **Requirement Coverage (40%)** — breadth: what fraction of every
  extracted requirement (skill, experience, education, certification;
  both must-have and preferred) does the resume satisfy at all.
- **Keyword & Terminology Alignment (25%)** — a raw, presence-only
  keyword-scan signal over the JD's own required/preferred skill
  vocabulary, independent of *how* well each skill is demonstrated. This
  models the literal keyword-matching behavior real ATS parsers are
  known for, as a signal distinct from Requirement Coverage's
  matched/partial/missing structural verdicts.
- **Resume Evidence & Experience (25%)** — depth: for skill and
  experience requirements specifically, how strongly the resume
  demonstrates them (professional/project usage vs. a bare skills-list
  mention; years comfortably above vs. below a stated minimum). Skill
  status here is the same `matched`/`partial`/`missing` verdict
  `engine.py` already computes (demonstrated mentions outside a skills
  section vs. skills-section-only vs. absent) — this module does not
  re-derive evidence strength, only aggregates it, per this ticket's
  requirement that evidence strength distinguish demonstrated
  professional/project experience from simple skills-section presence.
- **Structure & Parseability (10%)** — a fixed, presence-only checklist
  (contact info, standard section headings, bullet-point formatting, no
  detected structural anti-patterns) of whether a resume is even
  legible to an ATS parser. Every check is boolean/presence-based, never
  a function of resume length or word count, so a longer resume gets no
  scoring advantage over a shorter one that covers the same signals
  (this ticket's resume-length-neutrality requirement).

Required-requirement guardrail (AJI-020): a resume that fails to
demonstrate its must-have requirements must never score highly overall
merely because its keywords/evidence/structure look good. Rather than
inventing an arbitrary penalty amount (explicitly disallowed by this
ticket), the guardrail is a mathematical ceiling: the overall score can
never exceed the resume's own must-have coverage percentage (the same
`matched=1.0/partial=0.5/missing=0.0` point scale Requirement Coverage
already uses, scoped to must-have requirements only). This mirrors the
precedent already established for Hard Eligibility vs. Job Match/ATS
Alignment in docs/ARCHITECTURE.md ("a high ATS/Job Match score must
never override a hard eligibility constraint") — here applied *within*
the ATS score itself, as a ceiling rather than a separate gate, since
ATS Alignment (unlike Hard Eligibility) always produces a graded score,
never a pass/fail.

Confidence aggregation (`compute_overall_confidence`) is unchanged by
AJI-020 — it reflects confidence in the engine's own per-requirement
evidence interpretation and has no dependency on the scoring formula.
"""

from __future__ import annotations

from collections import Counter

from services.ats_alignment.contracts import (
    Confidence,
    JobRequirementItem,
    RequirementAlignment,
    ScoreComponent,
)
from services.ats_alignment.resume_adapter import ResumeEvidenceProfile
from services.ats_alignment.weights import SCORE_WEIGHTS


_STATUS_POINTS: dict[str, float] = {
    "matched": 1.0,
    "partial": 0.5,
    "missing": 0.0,
}


def _coverage_ratio(results: list[RequirementAlignment]) -> float | None:
    """Average `_STATUS_POINTS` over `results`, as a 0-100 percentage.

    Returns None (never 0.0) when `results` is empty, so callers can
    distinguish "nothing to check, don't penalize" from "checked and
    scored zero" — the same convention
    `services.job_matching.scorer.score_experience`'s
    "no requirements -> full credit" rule protects against, applied here
    via an explicit None rather than an implicit full-credit default,
    since an empty component must never silently inflate the weighted
    sum below.
    """
    if not results:
        return None

    total_points = sum(_STATUS_POINTS[result.status] for result in results)
    return round(100 * total_points / len(results), 2)


# ---------------------------------------------------------------------------
# Requirement Coverage (40%)
# ---------------------------------------------------------------------------

def compute_requirement_coverage(
    requirement_results: list[RequirementAlignment],
) -> ScoreComponent:
    """
    Breadth of coverage across every requirement (any type, either
    category) — the direct successor to AJI-013's placeholder formula,
    now scoped to exactly one of four weighted dimensions instead of
    standing in for the whole score.
    """
    score = _coverage_ratio(requirement_results) or 0.0

    return ScoreComponent(
        name="requirement_coverage",
        weight=SCORE_WEIGHTS["requirement_coverage"],
        score=score,
        explanation=(
            "Share of all extracted job requirements (must-have and "
            "preferred; skills, experience, education, certifications) "
            "that this resume matches or partially matches."
        ),
    )


def compute_must_have_ceiling(
    requirement_results: list[RequirementAlignment],
) -> float | None:
    """
    The required-requirement guardrail: the maximum overall score a
    resume may receive, based solely on its own must-have coverage.
    Returns None when there are no must-have requirements to check
    (nothing to gate on) — callers must not apply a ceiling in that
    case.
    """
    must_have_results = [
        result for result in requirement_results if result.category == "must_have"
    ]

    return _coverage_ratio(must_have_results)


# ---------------------------------------------------------------------------
# Keyword & Terminology Alignment (25%)
# ---------------------------------------------------------------------------

def compute_keyword_alignment(
    job_requirements: list[JobRequirementItem],
    resume: ResumeEvidenceProfile,
) -> ScoreComponent:
    """
    Presence-only overlap between the JD's required/preferred skill
    vocabulary and the resume's own canonical skill list.

    Both sides are already resolved through `services.skills`'
    canonical vocabulary before reaching this function (job-side via
    AJI-012 extraction, resume-side via
    `resume_adapter.build_resume_evidence_profile`), which is what
    supplies exact, normalized, and acronym matching for free (e.g.
    "k8s"/"kubernetes", "GCP"/"Google Cloud Platform" already resolve to
    one canonical identity upstream). Because every canonical skill's
    alias set is curated individually, a related-but-different
    technology (e.g. "react" vs. a hypothetical "react native") is never
    silently treated as the same skill — this is the concrete mechanism
    that satisfies this ticket's "do not conflate related-but-different
    technologies" requirement, not a new heuristic invented here.

    Membership is boolean (present or absent), never a mention count, so
    a resume that repeats a keyword many times scores identically to one
    that mentions it once — required for resume-length neutrality.
    """
    jd_skills = {
        requirement.canonical_skill
        for requirement in job_requirements
        if requirement.requirement_type == "skill" and requirement.canonical_skill
    }

    if not jd_skills:
        return ScoreComponent(
            name="keyword_terminology_alignment",
            weight=SCORE_WEIGHTS["keyword_terminology_alignment"],
            score=100.0,
            explanation=(
                "This job listed no specific skill keywords to check "
                "against the resume."
            ),
        )

    resume_skills = set(resume.skills)
    overlap = jd_skills & resume_skills

    score = round(100 * len(overlap) / len(jd_skills), 2)

    return ScoreComponent(
        name="keyword_terminology_alignment",
        weight=SCORE_WEIGHTS["keyword_terminology_alignment"],
        score=score,
        explanation=(
            f"Resume contains {len(overlap)} of {len(jd_skills)} "
            "distinct skill terms/keywords mentioned in the job "
            "description."
        ),
    )


# ---------------------------------------------------------------------------
# Resume Evidence & Experience (25%)
# ---------------------------------------------------------------------------

def compute_evidence_experience(
    requirement_results: list[RequirementAlignment],
) -> ScoreComponent:
    """
    Depth of evidence for skill and experience requirements specifically
    (education/certification are breadth-only checks handled by
    Requirement Coverage, not evidence-strength checks — a degree or
    certification has no "demonstrated vs. skills-only" distinction the
    way a skill or a years-of-experience claim does).

    Reuses `engine.py`'s existing status verdicts rather than
    re-deriving evidence strength: `matched` already means demonstrated
    professional/project usage (skill) or years at/above the minimum
    (experience); `partial` already means a skills-section-only mention
    or years below the minimum. This module only aggregates that
    distinction into a score.
    """
    results = [
        result
        for result in requirement_results
        if result.requirement_type in ("skill", "experience")
    ]

    score = _coverage_ratio(results)

    if score is None:
        return ScoreComponent(
            name="resume_evidence_experience",
            weight=SCORE_WEIGHTS["resume_evidence_experience"],
            score=100.0,
            explanation=(
                "This job had no skill or experience requirements to "
                "verify evidence strength against."
            ),
        )

    return ScoreComponent(
        name="resume_evidence_experience",
        weight=SCORE_WEIGHTS["resume_evidence_experience"],
        score=score,
        explanation=(
            "Strength of evidence for required/preferred skills "
            "(demonstrated in experience/project content vs. listed "
            "only in a skills section) and stated years of experience "
            "against any minimum-years requirements."
        ),
    )


# ---------------------------------------------------------------------------
# Structure & Parseability (10%)
# ---------------------------------------------------------------------------

# A fixed, equally-weighted checklist of presence-only parseability
# signals. None of these are a function of resume length/word count —
# each is a single boolean derived from
# apps.api.services.resume_ai.deterministic's existing section/contact/
# bullet/structural-finding detection (AJI-010), reused as-is rather
# than a second resume-structure parser.
_PARSEABILITY_CHECK_COUNT = 5


def compute_structure_parseability(resume: ResumeEvidenceProfile) -> ScoreComponent:
    checks = {
        "has_contact_info": resume.has_contact_info,
        "has_experience_section": "experience" in resume.detected_sections,
        "has_skills_section": "skills" in resume.detected_sections,
        "uses_bullet_points": resume.has_bullet_points,
        "consistent_heading_style": (
            "heading_style_inconsistency" not in resume.structural_finding_types
        ),
    }

    passed = sum(1 for value in checks.values() if value)
    score = round(100 * passed / _PARSEABILITY_CHECK_COUNT, 2)

    failed = [name for name, value in checks.items() if not value]
    if failed:
        explanation = (
            "Resume format checks not detected: " + ", ".join(sorted(failed)) + "."
        )
    else:
        explanation = "Resume passes every structural parseability check."

    return ScoreComponent(
        name="structure_parseability",
        weight=SCORE_WEIGHTS["structure_parseability"],
        score=score,
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Overall aggregation
# ---------------------------------------------------------------------------

def compute_overall_score(
    requirement_results: list[RequirementAlignment],
    job_requirements: list[JobRequirementItem],
    resume: ResumeEvidenceProfile,
) -> tuple[float, list[ScoreComponent], float | None] | None:
    """
    Compute the full weighted ATS Alignment score.

    Returns None when there is nothing to score at all (AJI-013 section
    19, unchanged: the caller must never persist a fabricated score for
    a Job Intelligence snapshot with no analyzable requirements).

    Otherwise returns `(overall_score, components, must_have_ceiling)`:
    - `overall_score` is `sum(component.weighted_score)`, capped at
      `must_have_ceiling` when one applies (see `compute_must_have_ceiling`).
    - `components` always has exactly four entries, one per
      `services.ats_alignment.weights.SCORE_WEIGHTS` key, so a caller
      can render/persist the full breakdown even when a given dimension
      had nothing to check (in which case it is neutral/excluded from
      penalizing the score, per each component function's own doc).
    """
    if not requirement_results:
        return None

    components = [
        compute_requirement_coverage(requirement_results),
        compute_keyword_alignment(job_requirements, resume),
        compute_evidence_experience(requirement_results),
        compute_structure_parseability(resume),
    ]

    weighted_sum = round(
        sum(component.weighted_score for component in components), 2
    )

    must_have_ceiling = compute_must_have_ceiling(requirement_results)

    overall_score = weighted_sum
    if must_have_ceiling is not None:
        overall_score = min(overall_score, must_have_ceiling)

    return round(overall_score, 2), components, must_have_ceiling


def compute_overall_confidence(
    requirement_results: list[RequirementAlignment],
) -> Confidence | None:
    """
    Deterministic aggregation of per-requirement analysis confidence.

    This reflects confidence in the ATS engine's own evidence
    interpretation (per-requirement), never an employability/hiring
    prediction (AJI-013 section 11). Unchanged by AJI-020's scoring
    formula replacement.
    """
    if not requirement_results:
        return None

    counts = Counter(result.confidence for result in requirement_results)
    total = len(requirement_results)

    if counts["low"] / total > 0.3:
        return "low"

    if counts["high"] == total:
        return "high"

    return "medium"
