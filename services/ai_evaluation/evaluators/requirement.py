"""Requirement Intelligence evaluation (AJI-020A contract).

Covers the four-tier requirement model as it reaches consumers
(required/preferred skill items, experience), the AND/OR relationship
groups that carry explicit alternatives such as "PyTorch or TensorFlow",
screening constraints, source-span provenance, and the JD
prompt-injection diagnostics this capability already produces.
"""

from __future__ import annotations

from collections.abc import Callable

from services.ai_evaluation import pipelines
from services.ai_evaluation.dataset import EvaluationDataset, JobCase
from services.ai_evaluation.evaluators.job import (
    score_experience_years,
    score_skill_tiers,
)
from services.ai_evaluation.grounding import is_grounded, span_grounded
from services.ai_evaluation.metrics import SetTally, Tally, count, ratio
from services.ai_evaluation.results import CapabilityResult


def _skill_items(output, importance: str) -> set[str]:
    return {
        item.canonical_terms[0]
        for item in output.requirements
        if item.requirement_type == "skill"
        and item.importance == importance
        and item.canonical_terms
    }


def _groups(output) -> set[tuple[str, frozenset[str]]]:
    terms = {
        item.id: item.canonical_terms[0]
        for item in output.requirements
        if item.canonical_terms
    }
    return {
        (group.relationship, frozenset(terms[member] for member in group.member_ids if member in terms))
        for group in output.relationships
        if group.relationship in ("AND", "OR")
    }


def evaluate_requirement_intelligence(
    dataset: EvaluationDataset,
    run: Callable[[JobCase], object] = pipelines.run_requirement_intelligence,
    source_text: Callable[[JobCase], str] = pipelines.requirement_source_text,
) -> CapabilityResult:
    result = CapabilityResult(
        capability="requirement_intelligence",
        title="Requirement Intelligence (deterministic extraction)",
        mode="deterministic",
        stage=(
            "requirement_intelligence.deterministic.extract_deterministic + "
            "validator.build_requirement_intelligence_result (ai_semantics=None)"
        ),
    )

    required = SetTally()
    preferred = SetTally()
    tiers = Tally()
    experience = Tally()
    groups = SetTally()
    or_groups = SetTally()
    screening = SetTally()
    spans = Tally()
    raw_text_grounded = Tally()
    injection_tp = injection_fn = injection_fp = injection_tn = 0
    absent_violations = 0

    for job in dataset.jobs:
        result.add_case(job.id)
        gt = job.ground_truth

        try:
            output = run(job)
        except Exception as exc:
            result.error(job.id, exc)
            continue

        absent_violations += score_skill_tiers(
            result,
            job,
            required=_skill_items(output, "required"),
            preferred=_skill_items(output, "preferred"),
            required_tally=required,
            preferred_tally=preferred,
            tier_tally=tiers,
        )

        for level in ("required", "preferred"):
            score_experience_years(
                result, job, level=level,
                expected=getattr(gt, f"{level}_experience_years"),
                actual=[
                    item.experience.minimum_years
                    for item in output.requirements
                    if item.requirement_type == "experience"
                    and item.importance == level
                    and item.experience is not None
                ],
                tally=experience,
            )

        expected_groups = {
            (group.relationship, frozenset(group.members))
            for group in gt.requirement_groups
        }
        actual_groups = _groups(output)
        missing, spurious = (
            expected_groups - actual_groups,
            actual_groups - expected_groups,
        )
        groups.add(
            {f"{rel}{sorted(members)}" for rel, members in expected_groups},
            {f"{rel}{sorted(members)}" for rel, members in actual_groups},
        )
        or_groups.add(
            {str(sorted(members)) for rel, members in expected_groups if rel == "OR"},
            {str(sorted(members)) for rel, members in actual_groups if rel == "OR"},
        )

        for relationship, members in sorted(missing, key=str):
            result.find(
                "requirement_interpretation_error",
                job.id,
                f"Missing {relationship} group over {sorted(members)}",
            )

        for relationship, members in sorted(spurious, key=str):
            result.find(
                "requirement_interpretation_error",
                job.id,
                f"Unexpected {relationship} group over {sorted(members)}",
            )

        actual_screening = {item.constraint_type for item in output.screening_constraints}
        screening.add(gt.screening_constraint_types, actual_screening, label=job.id)

        for constraint in sorted(actual_screening - set(gt.screening_constraint_types)):
            result.find("unsupported_claim", job.id, f"Unexpected screening constraint '{constraint}'")

        for constraint in sorted(set(gt.screening_constraint_types) - actual_screening):
            result.find("extraction_error", job.id, f"Missed screening constraint '{constraint}'")

        text = source_text(job)

        for item in output.requirements:
            if item.source_span is not None:
                span = item.source_span
                if not spans.add(span_grounded(span.text, span.start, span.end, text)):
                    result.find(
                        "grounding_failure",
                        job.id,
                        f"Source span for {item.id} does not match the JD text at "
                        f"[{span.start}:{span.end}]",
                    )

            if not raw_text_grounded.add(is_grounded(item.raw_text, text)):
                result.find(
                    "grounding_failure",
                    job.id,
                    f"Requirement {item.id} raw_text not in JD text: {item.raw_text!r}",
                )

        expected_injection = gt.injection is not None
        detected = output.security.prompt_injection_detected

        if expected_injection and detected:
            injection_tp += 1
        elif expected_injection:
            injection_fn += 1
            result.find("prompt_injection", job.id, "Injection payload was not detected")
        elif detected:
            injection_fp += 1
            result.find(
                "human_review",
                job.id,
                "Injection flagged on a JD labelled clean: "
                + ", ".join(signal.pattern_label for signal in output.security.signals),
            )
        else:
            injection_tn += 1

    result.metrics = {
        **required.metrics("required_skill"),
        **preferred.metrics("preferred_skill"),
        "skill_tier_accuracy": tiers.metric(),
        "absent_probe_violations": count(absent_violations),
        "experience_years_accuracy": experience.metric(),
        **groups.metrics("relationship_group"),
        "or_group_recall": or_groups.recall(),
        **screening.metrics("screening_constraint"),
        "source_span_grounding_rate": spans.metric(),
        "raw_text_grounding_rate": raw_text_grounded.metric(),
        "injection_detection_recall": ratio(injection_tp, injection_tp + injection_fn),
        "injection_false_alarms": count(injection_fp),
    }
    result.extra = {
        "injection_confusion": {
            "true_positive": injection_tp,
            "false_negative": injection_fn,
            "false_positive": injection_fp,
            "true_negative": injection_tn,
        }
    }
    result.notes = [
        "Only AND/OR groups over canonical skills are labelled. MIN_COUNT and "
        "EQUIVALENT groups are not scored (no dataset case states them).",
        "'Tableau or Power BI' (J2) is an alternative outside the canonical "
        "vocabulary and is deliberately not labelled as a group.",
    ]
    return result
