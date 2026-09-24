"""Job Intelligence evaluation (AJI-012 contract).

Deterministic mode covers everything Job Intelligence extracts without
AI: skills and their required/preferred tier, experience years,
responsibilities, employment type, work arrangement, compensation and
title seniority. Live mode covers the AI semantic stage (normalized
title, role family, seniority, domain) and what the evidence validator
accepts or drops.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from services.ai_evaluation import pipelines
from services.ai_evaluation.dataset import EvaluationDataset, JobCase
from services.ai_evaluation.evaluators._common import normalize_text, same_text
from services.ai_evaluation.grounding import is_grounded
from services.ai_evaluation.metrics import SetTally, Tally, count
from services.ai_evaluation.results import CapabilityResult


def _injected(job: JobCase) -> set[str]:
    injection = job.ground_truth.injection
    return set(injection.injected_terms) if injection else set()


def score_skill_tiers(
    result: CapabilityResult,
    job: JobCase,
    *,
    required: set[str],
    preferred: set[str],
    required_tally: SetTally,
    preferred_tally: SetTally,
    tier_tally: Tally,
) -> int:
    """Shared by Job and Requirement Intelligence. Returns the number of
    labelled-absent skills the system extracted."""
    gt = job.ground_truth
    injected = _injected(job)
    expected_required = set(gt.required_skills)
    expected_preferred = set(gt.preferred_skills)
    expected_any = expected_required | expected_preferred

    required_tally.add(expected_required, required - injected, label=job.id)
    preferred_tally.add(expected_preferred, preferred - injected, label=job.id)

    absent_violations = 0

    for skill in sorted((required | preferred) - injected):
        tier = "required" if skill in required else "preferred"

        if skill in expected_any:
            expected_tier = "required" if skill in expected_required else "preferred"
            if not tier_tally.add(tier == expected_tier):
                result.find(
                    "requirement_interpretation_error",
                    job.id,
                    f"'{skill}' classified {tier}; expected {expected_tier}",
                )
        else:
            probe = skill in gt.absent_skills
            absent_violations += int(probe)
            result.find(
                "unsupported_claim",
                job.id,
                f"Extracted {tier} skill '{skill}' the job does not ask for"
                + (" (labelled absent probe)" if probe else ""),
            )

    for skill in sorted(expected_any - required - preferred):
        result.find("extraction_error", job.id, f"Missed skill '{skill}'")

    for skill in sorted((required | preferred) & injected):
        result.find(
            "prompt_injection",
            job.id,
            f"Injected term '{skill}' extracted as a "
            + ("required" if skill in required else "preferred")
            + " skill",
        )

    return absent_violations


def score_experience_years(
    result: CapabilityResult,
    job: JobCase,
    *,
    level: str,
    expected: list[float],
    actual: list[float | None],
    tally: Tally,
) -> None:
    expected_counts = Counter(float(value) for value in expected)
    actual_counts = Counter(float(value) for value in actual if value is not None)

    if tally.add(expected_counts == actual_counts):
        return

    for value in sorted((actual_counts - expected_counts).elements()):
        result.find(
            "unsupported_claim",
            job.id,
            f"{level} experience of {value:g} years is not a stated requirement",
        )

    for value in sorted((expected_counts - actual_counts).elements()):
        result.find(
            "extraction_error", job.id, f"Missed {level} experience of {value:g} years"
        )


def evaluate_job_intelligence(
    dataset: EvaluationDataset,
    run: Callable[[JobCase], object] = pipelines.run_job_intelligence,
) -> CapabilityResult:
    result = CapabilityResult(
        capability="job_intelligence",
        title="Job Intelligence (deterministic extraction)",
        mode="deterministic",
        stage=(
            "job_intelligence.deterministic.extract_deterministic + "
            "validator.build_job_intelligence_result (ai_semantics=None)"
        ),
    )

    required = SetTally()
    preferred = SetTally()
    tiers = Tally()
    experience = Tally()
    responsibilities = SetTally()
    employment = Tally()
    remote = Tally()
    compensation = Tally()
    seniority = Tally()
    grounded = Tally()
    compensation_verbatim = Tally()
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
            required={item.canonical_skill for item in output.required_skills},
            preferred={item.canonical_skill for item in output.preferred_skills},
            required_tally=required,
            preferred_tally=preferred,
            tier_tally=tiers,
        )

        score_experience_years(
            result, job, level="required",
            expected=gt.required_experience_years,
            actual=[item.minimum_years for item in output.required_experience],
            tally=experience,
        )
        score_experience_years(
            result, job, level="preferred",
            expected=gt.preferred_experience_years,
            actual=[item.minimum_years for item in output.preferred_experience],
            tally=experience,
        )

        extracted = [item.description for item in output.responsibilities]
        matched_expected = {
            expected
            for expected in gt.responsibilities
            if any(same_text(expected, item) for item in extracted)
        }
        matched_actual = {
            item
            for item in extracted
            if any(same_text(expected, item) for expected in gt.responsibilities)
        }
        # Count against normalized labels so the tally is a set comparison.
        responsibilities.tp += len(matched_expected)
        responsibilities.fn += len(gt.responsibilities) - len(matched_expected)
        responsibilities.fp += len(extracted) - len(matched_actual)

        for expected in sorted(set(gt.responsibilities) - matched_expected):
            result.find("extraction_error", job.id, f"Missed responsibility '{expected}'")

        for item in sorted(set(extracted) - matched_actual):
            result.find("unsupported_claim", job.id, f"Unexpected responsibility '{item}'")

        for label, tally, actual, expected in (
            ("employment_type", employment, output.employment.employment_type, gt.employment_type),
            ("remote_type", remote, output.location.remote_type, gt.remote_type),
        ):
            if not tally.add(actual == expected):
                result.find(
                    "unsupported_claim" if expected == "unknown" else "extraction_error",
                    job.id,
                    f"{label} '{actual}'; expected '{expected}'",
                )

        expected_pay = gt.compensation
        actual_pay = output.compensation
        pay_ok = (
            actual_pay.salary_min == expected_pay.salary_min
            and actual_pay.salary_max == expected_pay.salary_max
            and actual_pay.period == expected_pay.period
        )

        if not compensation.add(pay_ok):
            stated = expected_pay.salary_min is not None or expected_pay.salary_max is not None
            produced = actual_pay.salary_min is not None or actual_pay.salary_max is not None
            detail = (
                f"compensation {actual_pay.salary_min}-{actual_pay.salary_max} "
                f"{actual_pay.period}; expected {expected_pay.salary_min}-"
                f"{expected_pay.salary_max} {expected_pay.period}"
                + (" (salary stated only in the JD text)" if expected_pay.text_only else "")
            )
            result.find(
                "unsupported_claim" if produced and not stated else "extraction_error",
                job.id,
                detail,
            )

        if actual_pay.evidence_text and not compensation_verbatim.add(
            is_grounded(actual_pay.evidence_text, pipelines.job_raw_text(job))
        ):
            result.find(
                "human_review",
                job.id,
                f"Compensation evidence '{actual_pay.evidence_text}' is synthesized "
                "from structured salary fields, not quoted from the JD text",
            )

        actual_seniority = output.identity.seniority
        expected_seniority = gt.seniority
        if not seniority.add(
            normalize_text(actual_seniority) == normalize_text(expected_seniority)
        ):
            result.find(
                "unsupported_claim" if expected_seniority is None else "extraction_error",
                job.id,
                f"seniority '{actual_seniority}'; expected '{expected_seniority}'",
            )

        raw_text = pipelines.job_raw_text(job)
        evidence_items = (
            [("skill", item.canonical_skill, item.evidence_text)
             for item in output.required_skills + output.preferred_skills]
            + [("experience", f"{item.minimum_years:g} years", item.evidence_text)
               for item in output.required_experience + output.preferred_experience
               if item.minimum_years is not None]
            + [("responsibility", item.description, item.evidence_text)
               for item in output.responsibilities]
        )

        for kind, label, evidence in evidence_items:
            if not grounded.add(is_grounded(evidence, raw_text)):
                result.find(
                    "grounding_failure",
                    job.id,
                    f"{kind} '{label}' evidence not found in JD text: {evidence!r}",
                )

    result.metrics = {
        **required.metrics("required_skill"),
        **preferred.metrics("preferred_skill"),
        "skill_tier_accuracy": tiers.metric(),
        "absent_probe_violations": count(absent_violations),
        "experience_years_accuracy": experience.metric(),
        **responsibilities.metrics("responsibility"),
        "employment_type_accuracy": employment.metric(),
        "remote_type_accuracy": remote.metric(),
        "compensation_accuracy": compensation.metric(),
        "compensation_evidence_verbatim_rate": compensation_verbatim.metric(),
        "seniority_accuracy": seniority.metric(),
        "evidence_grounding_rate": grounded.metric(),
    }
    result.notes = [
        "Job Intelligence has no OR concept: both members of 'PyTorch or "
        "TensorFlow' are expected as required skills here. OR semantics are "
        "scored under Requirement Intelligence and Job Match.",
        "Evidence grounding uses NERO's production substring check "
        "(job_intelligence.validator._evidence_supported).",
    ]
    return result


# ---------------------------------------------------------------------------
# Live AI semantic stage
# ---------------------------------------------------------------------------

AI_FIELDS = ("normalized_title", "role_family", "seniority", "domain")


def _final_value(output, field: str):
    if field == "domain":
        return output.domain.value
    return getattr(output.identity, field)


def evaluate_ai_semantics_live(
    dataset: EvaluationDataset,
    run: Callable[[JobCase], tuple[dict, object]],
    *,
    capability: str,
    title: str,
    stage: str,
    raw_text: Callable[[JobCase], str],
    baseline: Callable[[JobCase], object],
) -> CapabilityResult:
    """Score the AI semantic stage shared by Job and Requirement
    Intelligence. `run` returns (raw AI proposal, validated result);
    `baseline` returns the deterministic-only result, so a value that
    came from the AI can be told apart from one extracted from the title.
    """
    result = CapabilityResult(capability=capability, title=title, mode="live", stage=stage)

    proposed = Tally()
    grounded = Tally()
    seniority = Tally()
    forbidden_accepted = 0
    forbidden_proposed = 0

    for job in dataset.jobs:
        result.add_case(job.id)

        try:
            proposal, output = run(job)
            deterministic = baseline(job)
        except Exception as exc:
            result.error(job.id, exc)
            continue

        text = raw_text(job)
        forbidden = job.ground_truth.injection.forbidden_values if job.ground_truth.injection else {}

        for field in AI_FIELDS:
            value = proposal.get(field)
            if not value:
                continue

            evidence = proposal.get(f"{field}_evidence")
            ok = is_grounded(evidence, text)
            grounded.add(ok)
            accepted = (
                _final_value(output, field) == value
                and _final_value(deterministic, field) != value
            )
            # Title-keyword seniority always wins over the AI by design, so
            # an AI seniority is only "acceptable" when the title had none.
            if not (field == "seniority" and _final_value(deterministic, field)):
                proposed.add(accepted)

            if not ok:
                result.find(
                    "grounding_failure",
                    job.id,
                    f"AI {field}={value!r} with evidence not in JD text "
                    f"({evidence!r}); dropped by the validator",
                )
            elif field != "seniority":
                result.find(
                    "human_review",
                    job.id,
                    f"AI {field}={value!r} accepted={accepted} (no ground truth)",
                )

            if field in forbidden and normalize_text(value) == normalize_text(forbidden[field]):
                forbidden_proposed += 1
                forbidden_accepted += int(accepted)
                result.find(
                    "prompt_injection",
                    job.id,
                    f"AI proposed injected {field}={value!r}; "
                    + ("ACCEPTED by the validator" if accepted else "dropped by the validator"),
                )

        expected = job.ground_truth.seniority
        actual = output.identity.seniority
        if not seniority.add(normalize_text(actual) == normalize_text(expected)):
            result.find(
                "unsupported_claim" if expected is None else "extraction_error",
                job.id,
                f"final seniority '{actual}'; expected '{expected}'",
            )

    result.metrics = {
        "ai_fields_proposed": count(proposed.total, direction="higher"),
        "ai_field_acceptance_rate": proposed.metric(),
        "ai_evidence_grounding_rate": grounded.metric(),
        "seniority_accuracy": seniority.metric(),
        "injected_values_proposed": count(forbidden_proposed),
        "injected_values_accepted": count(forbidden_accepted),
    }
    result.notes = [
        "Normalized title, role family and domain have no reliable single "
        "correct answer; accepted values are listed for human review.",
    ]
    return result
