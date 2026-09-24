"""General Resume Score evaluation (AJI-027), against its approved behavior.

The approved score has no threshold, band or "good score". This
evaluation therefore does not judge the overall number. It checks the
parts of the approved definition that have an objective answer in the
source text: the structure checks (experience/education/skills sections,
email, phone, bullets) and that scoring the same resume twice gives the
same result. Overall and component scores are reported descriptively.
"""

from __future__ import annotations

from collections.abc import Callable

from apps.api.services.general_resume.scoring import (
    score_resume,
    structure_checks,
)
from services.ai_evaluation import pipelines
from services.ai_evaluation.dataset import EvaluationDataset, ResumeCase
from services.ai_evaluation.metrics import Tally
from services.ai_evaluation.results import CapabilityResult


def evaluate_general_resume_score(
    dataset: EvaluationDataset,
    analyze: Callable[[ResumeCase], object] = pipelines.analyze_resume,
) -> CapabilityResult:
    result = CapabilityResult(
        capability="general_resume_score",
        title="General Resume Score (approved AJI-027 behavior)",
        mode="deterministic",
        stage="general_resume.scoring.score_resume over the deterministic analysis",
    )

    checks_tally = Tally()
    determinism = Tally()
    scores: dict[str, dict] = {}

    for resume in dataset.resumes:
        result.add_case(resume.id)
        gt = resume.ground_truth

        try:
            analysis = analyze(resume)
            first = score_resume(analysis)
            second = score_resume(analyze(resume))
            checks = structure_checks(analysis)
        except Exception as exc:
            result.error(resume.id, exc)
            continue

        expected = {
            "experience section": gt.sections.experience,
            "education section": gt.sections.education,
            "skills section": gt.sections.skills,
            "email": gt.has_email,
            "phone": gt.has_phone,
            "bullets": gt.has_bullets,
        }
        actual = {
            "experience section": checks.has_sections["experience"],
            "education section": checks.has_sections["education"],
            "skills section": checks.has_sections["skills"],
            "email": checks.has_email,
            "phone": checks.has_phone,
            "bullets": checks.has_bullets,
        }

        for name, want in expected.items():
            if not checks_tally.add(actual[name] == want):
                result.find(
                    "unsupported_claim" if actual[name] else "extraction_error",
                    resume.id,
                    f"Structure check '{name}' = {actual[name]}; expected {want}",
                )

        same = first.overall_score == second.overall_score and [
            component.model_dump() for component in first.components
        ] == [component.model_dump() for component in second.components]

        if not determinism.add(same):
            result.find("error", resume.id, "Scoring the same resume twice differed")

        scores[resume.id] = {
            "overall_score": first.overall_score,
            "components": {
                component.key: (
                    component.score if component.status == "scored" else component.status
                )
                for component in first.components
            },
        }

    result.metrics = {
        "structure_check_accuracy": checks_tally.metric(),
        "score_determinism": determinism.metric(),
    }
    result.extra = {"scores": scores}
    result.notes = [
        "Scores are descriptive only; AJI-031 introduces no threshold or band.",
        "The 'consistent heading capitalization' check has no objective label "
        "and is not scored.",
    ]
    return result
