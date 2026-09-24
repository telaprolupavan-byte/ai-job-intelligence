"""The General Resume Score (AJI-027): pure, deterministic, job-independent.

`score_resume(analysis)` takes only the output of the existing
deterministic resume analyzer
(`apps.api.services.resume_ai.deterministic.analyze_resume_deterministically`)
for one resume's text. It takes no job, requirement, preference or ATS
input, makes no AI call, and adds no detection rule of its own - every
signal below is one the analyzer already produces.

Formula (Product Owner approved for AJI-027):

- Five components, each 0-100 and each a **ratio**, so a longer resume
  does not score higher merely for being longer (the AJI-020
  length-neutrality rule):

  | Component | Definition |
  |---|---|
  | Structure & parseability | checks passed / 7: experience, education and skills sections present; an email; a phone number; bullets detected; consistent heading capitalization |
  | Action-oriented writing | bullets starting with an action verb / all bullets |
  | Measurable impact | experience/project bullets with quantification / those bullets |
  | Clarity | 1 - bullets with a weak phrase / all bullets |
  | Skill evidence | skills demonstrated outside the skills list / skills detected |

- Equal weights across the components that could be measured. A
  component with nothing to measure (zero bullets, zero recognized
  skills) is `insufficient_data`: excluded from the average, never
  scored as zero, and surfaced as an improvement area instead.
- Clarity counts weak phrases only. The analyzer's repeated-phrase signal
  counts any two-word sequence in two bullets (e.g. "for the"), which is
  too noisy to score; this was a Product Owner decision during AJI-027.
- No band, label, pass/fail split or threshold exists here or anywhere
  downstream.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.api.services.general_resume.contracts import ScoreComponent
from apps.api.services.resume_ai.deterministic import (
    DeterministicResumeAnalysis,
)


SCORING_VERSION = "1.0"

# Sections whose bullets are expected to describe outcomes.
IMPACT_SECTIONS = frozenset({"experience", "projects"})

CORE_SECTIONS = ("experience", "education", "skills")

COMPONENT_LABELS = {
    "structure": "Structure & parseability",
    "action_writing": "Action-oriented writing",
    "measurable_impact": "Measurable impact",
    "clarity": "Clarity",
    "skill_evidence": "Skill evidence",
}


@dataclass(frozen=True)
class StructureChecks:
    has_sections: dict[str, bool]
    has_email: bool
    has_phone: bool
    has_bullets: bool
    consistent_headings: bool

    @property
    def passed(self) -> int:
        return (
            sum(self.has_sections.values())
            + int(self.has_email)
            + int(self.has_phone)
            + int(self.has_bullets)
            + int(self.consistent_headings)
        )

    @property
    def total(self) -> int:
        return len(self.has_sections) + 4


@dataclass(frozen=True)
class ScoreResult:
    overall_score: float
    components: list[ScoreComponent]


def structure_checks(analysis: DeterministicResumeAnalysis) -> StructureChecks:
    present = {section.name for section in analysis.sections}
    finding_types = {
        finding.get("type") for finding in analysis.structural_findings
    }

    return StructureChecks(
        has_sections={name: name in present for name in CORE_SECTIONS},
        has_email=bool(analysis.emails),
        has_phone=bool(analysis.phones),
        has_bullets=(
            "no_bullets_detected" not in finding_types
            and bool(analysis.bullets)
        ),
        consistent_headings="heading_style_inconsistency" not in finding_types,
    )


def impact_bullets(analysis: DeterministicResumeAnalysis) -> list:
    return [
        bullet
        for bullet in analysis.bullets
        if bullet.section in IMPACT_SECTIONS
    ]


def _ratio_component(
    *,
    key: str,
    numerator: int,
    denominator: int,
    detail: str,
    empty_detail: str,
) -> ScoreComponent:
    if denominator == 0:
        return ScoreComponent(
            key=key,
            label=COMPONENT_LABELS[key],
            status="insufficient_data",
            score=None,
            weight=0.0,
            numerator=0,
            denominator=0,
            detail=empty_detail,
        )

    return ScoreComponent(
        key=key,
        label=COMPONENT_LABELS[key],
        status="scored",
        score=round(100.0 * numerator / denominator, 1),
        weight=0.0,
        numerator=numerator,
        denominator=denominator,
        detail=detail.format(numerator=numerator, denominator=denominator),
    )


def score_resume(analysis: DeterministicResumeAnalysis) -> ScoreResult:
    checks = structure_checks(analysis)
    bullets = analysis.bullets
    outcome_bullets = impact_bullets(analysis)

    skill_statuses = [
        evidence.get("status")
        for evidence in analysis.skill_evidence.values()
    ]

    components = [
        _ratio_component(
            key="structure",
            numerator=checks.passed,
            denominator=checks.total,
            detail="{numerator} of {denominator} structure checks passed.",
            empty_detail="",
        ),
        _ratio_component(
            key="action_writing",
            numerator=sum(1 for bullet in bullets if bullet.has_action_verb),
            denominator=len(bullets),
            detail=(
                "{numerator} of {denominator} bullets start with an "
                "action verb."
            ),
            empty_detail="No bullet points were detected to measure.",
        ),
        _ratio_component(
            key="measurable_impact",
            numerator=sum(
                1 for bullet in outcome_bullets if bullet.has_quantification
            ),
            denominator=len(outcome_bullets),
            detail=(
                "{numerator} of {denominator} experience and project "
                "bullets include a measurable result."
            ),
            empty_detail=(
                "No experience or project bullets were detected to measure."
            ),
        ),
        _ratio_component(
            key="clarity",
            numerator=sum(1 for bullet in bullets if not bullet.weak_phrases),
            denominator=len(bullets),
            detail="{numerator} of {denominator} bullets avoid weak phrasing.",
            empty_detail="No bullet points were detected to measure.",
        ),
        _ratio_component(
            key="skill_evidence",
            numerator=sum(
                1 for status in skill_statuses if status == "demonstrated"
            ),
            denominator=len(skill_statuses),
            detail=(
                "{numerator} of {denominator} recognized skills are shown "
                "in use outside the skills list."
            ),
            empty_detail="No recognized skills were detected to measure.",
        ),
    ]

    scored = [
        component for component in components if component.status == "scored"
    ]

    # Structure always has a denominator, so `scored` is never empty.
    weight = round(1.0 / len(scored), 4)

    components = [
        component.model_copy(update={"weight": weight})
        if component.status == "scored"
        else component
        for component in components
    ]

    overall = round(
        sum(component.score for component in scored) / len(scored),
        1,
    )

    return ScoreResult(overall_score=overall, components=components)
