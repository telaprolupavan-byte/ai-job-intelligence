"""Resume <-> Job matching evaluation.

Two production consumers turn a resume and a job into matches and gaps:

- Job Match (`services.job_matching`, fed by Job Intelligence).
- Gap Analysis candidate selection (`gap_analysis.engine`, fed by ATS
  Alignment over Requirement Intelligence). Its optional AI stage only
  rewrites explanation text; it never changes which requirements are
  gaps, so the gap set is fully covered here.

Both are scored against the same hand-labelled expectations, including
explicit alternatives ("PyTorch or TensorFlow"): a satisfied alternative
group must not produce a gap for its unused member.
"""

from __future__ import annotations

from collections.abc import Callable

from services.ai_evaluation import pipelines
from services.ai_evaluation.dataset import (
    EvaluationDataset,
    JobCase,
    MatchCase,
    ResumeCase,
)
from services.ai_evaluation.evaluators._common import satisfied_group_members
from services.ai_evaluation.metrics import SetTally, Tally, count
from services.ai_evaluation.results import CapabilityResult


def score_groups(
    result: CapabilityResult,
    case: MatchCase,
    dataset: EvaluationDataset,
    *,
    gaps_by_level: dict[str, set[str]],
    or_tally: Tally,
    and_tally: Tally,
) -> None:
    """A group is handled correctly when a satisfied group reports no gap
    for any member and an unsatisfied group reports at least one."""
    relationships = {
        (group.level, frozenset(group.members)): group.relationship
        for group in dataset.job(case.job_id).ground_truth.requirement_groups
    }

    for group in case.expected.requirement_groups:
        relationship = relationships[(group.level, frozenset(group.members))]
        gapped = sorted(set(group.members) & gaps_by_level[group.level])
        correct = not gapped if group.satisfied else bool(gapped)
        tally = or_tally if relationship == "OR" else and_tally

        if not tally.add(correct):
            if group.satisfied:
                detail = (
                    f"'{' or '.join(group.members)}' is satisfied, but "
                    f"{gapped} reported as {group.level} gap(s): the alternative "
                    "is treated as a separate required item"
                    if relationship == "OR"
                    else f"AND group {group.members} satisfied but {gapped} reported as gaps"
                )
            else:
                detail = f"Unsatisfied {relationship} group {group.members} reported no gap"
            result.find(
                "matching_error" if relationship == "OR" else "requirement_interpretation_error",
                case.id,
                detail,
            )


def _score_gaps(
    result: CapabilityResult,
    case: MatchCase,
    *,
    level: str,
    expected: list[str],
    actual: set[str],
    tally: SetTally,
    what: str,
) -> None:
    alternatives = satisfied_group_members(case, level)
    false_positives, false_negatives = tally.add(expected, actual, label=case.id)

    for skill in sorted(false_positives):
        if skill in case.expected.not_credited:
            category, reason = "prompt_injection", " (term from a prompt-injection payload)"
        elif skill in alternatives:
            category, reason = "matching_error", " (unused member of a satisfied alternative group)"
        else:
            category, reason = "matching_error", ""
        result.find(category, case.id, f"'{skill}' reported as {level} {what}{reason}")

    for skill in sorted(false_negatives):
        category = "prompt_injection" if skill in case.expected.not_credited else "matching_error"
        result.find(category, case.id, f"Expected {level} {what} '{skill}' not reported")


def evaluate_job_match(
    dataset: EvaluationDataset,
    run: Callable[[ResumeCase, JobCase, MatchCase], object] = pipelines.run_job_match,
) -> CapabilityResult:
    result = CapabilityResult(
        capability="job_match",
        title="Resume <-> Job Match",
        mode="deterministic",
        stage=(
            "job_match_service._build_job_requirements (Job Intelligence) + "
            "services.job_matching.JobMatchingService.calculate_match"
        ),
    )

    required_gaps = SetTally()
    preferred_gaps = SetTally()
    matched = SetTally()
    or_groups = Tally()
    and_groups = Tally()
    evidence_type = Tally()
    rankings = Tally()
    injected_credited = 0
    scores: dict[str, float] = {}

    for case in dataset.match_cases:
        result.add_case(case.id)
        resume = dataset.resume(case.resume_id)
        job = dataset.job(case.job_id)

        try:
            output = run(resume, job, case)
        except Exception as exc:
            result.error(case.id, exc)
            continue

        scores[case.id] = output.score
        expected = case.expected
        gaps = {
            "required": {item.skill for item in output.must_have_gaps},
            "preferred": {item.skill for item in output.preferred_gaps},
        }
        actual_matched = {item.skill for item in output.must_have_matches} | {
            item.skill for item in output.preferred_matches
        }

        _score_gaps(result, case, level="required", expected=expected.required_gaps,
                    actual=gaps["required"], tally=required_gaps, what="gap")
        _score_gaps(result, case, level="preferred", expected=expected.preferred_gaps,
                    actual=gaps["preferred"], tally=preferred_gaps, what="gap")

        expected_matched = set(expected.required_matched) | set(expected.preferred_matched)
        false_positives, false_negatives = matched.add(
            expected_matched, actual_matched, label=case.id
        )

        for skill in sorted(false_positives):
            injected = skill in expected.not_credited
            injected_credited += int(injected)
            result.find(
                "prompt_injection" if injected else "unsupported_claim",
                case.id,
                f"Credited '{skill}' as matched"
                + (" from a resume prompt-injection payload" if injected else ""),
            )

        for skill in sorted(false_negatives):
            result.find("matching_error", case.id, f"Did not credit matched skill '{skill}'")

        score_groups(result, case, dataset, gaps_by_level=gaps,
                     or_tally=or_groups, and_tally=and_groups)

        demonstrated = set(resume.ground_truth.demonstrated_skills)
        for item in output.must_have_matches + output.preferred_matches:
            if item.skill not in resume.ground_truth.expected_skills:
                continue
            want = "experience" if item.skill in demonstrated else "explicit"
            if not evidence_type.add(item.evidence_type.value == want):
                result.find(
                    "matching_error",
                    case.id,
                    f"'{item.skill}' evidence type '{item.evidence_type.value}'; expected '{want}'",
                )

    for ranking in dataset.manifest.rankings:
        if ranking.higher not in scores or ranking.lower not in scores:
            continue
        higher, lower = scores[ranking.higher], scores[ranking.lower]
        if not rankings.add(higher > lower):
            result.find(
                "matching_error",
                ranking.higher,
                f"Scored {higher} for {ranking.higher}, not above {lower} for {ranking.lower}",
            )

    result.metrics = {
        **required_gaps.metrics("required_gap"),
        **preferred_gaps.metrics("preferred_gap"),
        **matched.metrics("matched_skill"),
        "alternative_or_group_correctness": or_groups.metric(),
        "and_group_correctness": and_groups.metric(),
        "evidence_type_accuracy": evidence_type.metric(),
        "ranking_correctness": rankings.metric(),
        "injected_skills_credited": count(injected_credited),
    }
    result.extra = {
        "scores": {
            case.id: {"score": scores.get(case.id), "category": case.category}
            for case in dataset.match_cases
        }
    }
    result.notes = [
        "Scores are reported for relative ordering only (strong vs. weak "
        "for the same job). No score threshold is introduced.",
        "profile_years_experience stands in for the user's profile field; "
        "target titles and job preferences are left empty.",
    ]
    return result


def evaluate_gap_analysis(
    dataset: EvaluationDataset,
    run: Callable[[ResumeCase, JobCase, MatchCase], list] = pipelines.run_gap_candidates,
) -> CapabilityResult:
    result = CapabilityResult(
        capability="gap_analysis",
        title="Gap Analysis (deterministic gap selection)",
        mode="deterministic",
        stage=(
            "ATS Alignment over Requirement Intelligence + "
            "gap_analysis.engine.select_gap_candidates"
        ),
    )

    missing = SetTally()
    partial = SetTally()
    or_groups = Tally()
    and_groups = Tally()
    experience_gaps: dict[str, list[str]] = {}

    for case in dataset.match_cases:
        result.add_case(case.id)
        resume = dataset.resume(case.resume_id)
        job = dataset.job(case.job_id)

        try:
            candidates = run(resume, job, case)
        except Exception as exc:
            result.error(case.id, exc)
            continue

        expected = case.expected
        level_of = {"must_have": "required", "preferred": "preferred"}
        skill_candidates = [item for item in candidates if item.requirement_type == "skill"]
        gaps = {"required": set(), "preferred": set()}
        partial_actual: set[str] = set()

        for item in skill_candidates:
            if item.status == "missing":
                gaps[level_of.get(item.category, "required")].add(item.requirement_text)
            else:
                partial_actual.add(item.requirement_text)

        experience_gaps[case.id] = [
            f"{item.requirement_text} ({item.status})"
            for item in candidates
            if item.requirement_type != "skill"
        ]

        for level in ("required", "preferred"):
            _score_gaps(
                result, case, level=level,
                expected=getattr(expected, f"{level}_gaps"),
                actual=gaps[level], tally=missing, what="missing gap",
            )

        demonstrated = set(resume.ground_truth.demonstrated_skills)
        expected_partial = {
            skill
            for skill in expected.required_matched + expected.preferred_matched
            if skill not in demonstrated
        }
        false_positives, false_negatives = partial.add(
            expected_partial, partial_actual, label=case.id
        )

        for skill in sorted(false_positives):
            category = "prompt_injection" if skill in expected.not_credited else "matching_error"
            result.find(category, case.id, f"'{skill}' reported as a partial gap")

        for skill in sorted(false_negatives):
            result.find(
                "matching_error",
                case.id,
                f"Listed-only skill '{skill}' not reported as a partial gap",
            )

        score_groups(result, case, dataset, gaps_by_level=gaps,
                     or_tally=or_groups, and_tally=and_groups)

    result.metrics = {
        **missing.metrics("missing_gap"),
        **partial.metrics("partial_gap"),
        "alternative_or_group_correctness": or_groups.metric(),
        "and_group_correctness": and_groups.metric(),
    }
    result.extra = {"non_skill_gap_candidates": experience_gaps}
    result.notes = [
        "Skill gaps only. Experience/education gap candidates are listed in "
        "'non_skill_gap_candidates' for review; years of experience come from "
        "the profile stand-in, not from the resume.",
        "A 'partial' gap is a skill the resume lists but does not demonstrate.",
    ]
    return result
