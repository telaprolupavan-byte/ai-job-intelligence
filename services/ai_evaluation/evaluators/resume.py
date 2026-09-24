"""Resume Intelligence evaluation.

Two stages are evaluated separately because they are separate code:

- Deterministic resume analysis
  (`resume_ai.deterministic.analyze_resume_deterministically`). It is
  the resume side of Job Match, ATS Alignment, Gap Analysis and the
  General Resume Score, so its skill extraction and "demonstrated vs.
  listed" evidence status drive every downstream result.
- The LLM Resume Intelligence stage (`resume_ai` provider + interpreter,
  `ResumeAIResult`). Live mode only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.ai_evaluation import pipelines
from services.ai_evaluation.dataset import EvaluationDataset, ResumeCase
from services.ai_evaluation.evaluators._common import same_text
from services.ai_evaluation.grounding import is_grounded
from services.ai_evaluation.metrics import SetTally, Tally, count
from services.ai_evaluation.results import CapabilityResult
from services.skills import normalize_skill
from services.skills.canonical import CANONICAL_SKILLS


def _injected(resume: ResumeCase) -> set[str]:
    injection = resume.ground_truth.injection
    return set(injection.injected_terms) if injection else set()


def evaluate_resume_deterministic(
    dataset: EvaluationDataset,
    analyze: Callable[[ResumeCase], Any] = pipelines.analyze_resume,
) -> CapabilityResult:
    result = CapabilityResult(
        capability="resume_intelligence_deterministic",
        title="Resume Intelligence: deterministic resume analysis",
        mode="deterministic",
        stage=(
            "resume_ai.deterministic.analyze_resume_deterministically: skills, "
            "skill evidence status, sections and contact details"
        ),
    )

    skills = SetTally()
    demonstrated = Tally()
    sections = Tally()
    contact = Tally()
    absent_violations = 0
    injected_credited = 0
    oov_total = 0

    for resume in dataset.resumes:
        result.add_case(resume.id)
        gt = resume.ground_truth

        try:
            analysis = analyze(resume)
        except Exception as exc:  # measured, never hidden
            result.error(resume.id, exc)
            continue

        injected = _injected(resume)
        detected = set(analysis.skills)
        ordinary = detected - injected

        false_positives, false_negatives = skills.add(
            gt.expected_skills, ordinary, label=resume.id
        )

        for skill in sorted(false_positives):
            probe = skill in gt.absent_skills
            absent_violations += int(probe)
            result.find(
                "unsupported_claim",
                resume.id,
                f"Extracted skill '{skill}' that the resume does not contain"
                + (" (labelled absent probe)" if probe else ""),
            )

        for skill in sorted(false_negatives):
            result.find(
                "extraction_error", resume.id, f"Missed skill '{skill}'"
            )

        for skill in sorted(detected & injected):
            injected_credited += 1
            status = analysis.skill_evidence.get(skill, {}).get("status")
            result.find(
                "prompt_injection",
                resume.id,
                f"Credited injected skill '{skill}' (evidence status: {status})",
            )

        for skill in sorted(set(gt.expected_skills) & detected):
            status = analysis.skill_evidence.get(skill, {}).get("status")
            is_demonstrated = status == "demonstrated"
            expected = skill in gt.demonstrated_skills

            if not demonstrated.add(is_demonstrated == expected):
                category = "unsupported_claim" if is_demonstrated else "extraction_error"
                result.find(
                    category,
                    resume.id,
                    f"Skill '{skill}' evidence status '{status}'; expected "
                    + ("demonstrated" if expected else "listed only"),
                )

        found_sections = {section.name for section in analysis.sections}

        for name, expected in gt.sections.model_dump().items():
            if not sections.add((name in found_sections) == expected):
                result.find(
                    "unsupported_claim" if not expected else "extraction_error",
                    resume.id,
                    f"Section '{name}' detected={name in found_sections}, expected={expected}",
                )

        for label, found, expected in (
            ("email", bool(analysis.emails), gt.has_email),
            ("phone", bool(analysis.phones), gt.has_phone),
        ):
            if not contact.add(found == expected):
                result.find(
                    "unsupported_claim" if found else "extraction_error",
                    resume.id,
                    f"{label} detected={found}, expected={expected}",
                )

        oov_total += len(gt.out_of_vocabulary_skills)

    result.metrics = {
        **skills.metrics("skill"),
        "unsupported_skill_claims": count(skills.fp),
        "absent_probe_violations": count(absent_violations),
        "demonstrated_status_accuracy": demonstrated.metric(),
        "section_detection_accuracy": sections.metric(),
        "contact_detection_accuracy": contact.metric(),
        "injected_skills_credited": count(injected_credited),
    }
    result.notes = [
        "Skill labels use NERO's canonical vocabulary (services.skills). "
        f"{oov_total} labelled out-of-vocabulary skills (e.g. Tableau) are "
        "listed in the dataset but not scored: the vocabulary is the "
        "documented contract.",
        "Injected skills (resume prompt-injection payloads) are excluded "
        "from precision/recall and counted under injected_skills_credited.",
        "Total years of experience is not scored: NERO does not extract it "
        "from resume text (Job Match reads the user's profile).",
        "No evidence-grounding metric here: this analyzer only reports "
        "literal pattern matches, so its errors are semantic (see findings).",
    ]
    return result


# ---------------------------------------------------------------------------
# Live LLM Resume Intelligence
# ---------------------------------------------------------------------------


def evaluate_resume_live(
    dataset: EvaluationDataset,
    run: Callable[[ResumeCase], dict],
) -> CapabilityResult:
    """Score a `ResumeAIResult`-shaped dict per resume. `run` calls the
    real provider in live mode; tests pass canned outputs."""
    result = CapabilityResult(
        capability="resume_intelligence_live",
        title="Resume Intelligence: LLM analysis (live)",
        mode="live",
        stage="resume_ai provider + ResumeAIInterpreter -> ResumeAIResult",
    )

    skills = SetTally()
    demonstrated = Tally()
    skill_evidence_grounded = Tally()
    finding_evidence_grounded = Tally()
    companies = Tally()
    institutions = Tally()
    projects = Tally()
    unsupported_entities = 0
    injected_credited = 0

    for resume in dataset.resumes:
        result.add_case(resume.id)
        gt = resume.ground_truth

        try:
            output = run(resume)
        except Exception as exc:
            result.error(resume.id, exc)
            continue

        text = resume.text
        decoding = output.get("decoding", {})
        review = output.get("review", {})
        injected = _injected(resume)

        claimed: dict[str, dict] = {}
        for item in decoding.get("skills", []):
            claimed.setdefault(normalize_skill(item.get("skill", "")), item)

        canonical_claims = {skill for skill in claimed if skill in CANONICAL_SKILLS}

        false_positives, false_negatives = skills.add(
            gt.expected_skills, canonical_claims - injected, label=resume.id
        )

        for skill in sorted(false_positives):
            result.find(
                "unsupported_claim",
                resume.id,
                f"LLM claimed skill '{skill}' not supported by the resume"
                + (" (labelled absent probe)" if skill in gt.absent_skills else ""),
            )

        for skill in sorted(false_negatives):
            result.find("extraction_error", resume.id, f"LLM missed skill '{skill}'")

        for skill in sorted(canonical_claims & injected):
            injected_credited += 1
            result.find(
                "prompt_injection",
                resume.id,
                f"LLM credited injected skill '{skill}' "
                f"(demonstrated={claimed[skill].get('demonstrated')})",
            )

        for skill in sorted(set(claimed) - set(CANONICAL_SKILLS)):
            if not is_grounded(skill, text):
                result.find(
                    "human_review",
                    resume.id,
                    f"Non-vocabulary skill claim '{skill}' does not appear verbatim",
                )

        for skill in sorted(canonical_claims & set(gt.expected_skills)):
            flag = bool(claimed[skill].get("demonstrated"))
            expected = skill in gt.demonstrated_skills
            if not demonstrated.add(flag == expected):
                result.find(
                    "unsupported_claim" if flag else "extraction_error",
                    resume.id,
                    f"LLM demonstrated={flag} for '{skill}', expected {expected}",
                )

        # The contract allows skill evidence to be a note ("only appears in
        # a skills list"), so an unquoted note is flagged for review rather
        # than failed.
        for skill, item in claimed.items():
            if not skill_evidence_grounded.add(is_grounded(item.get("evidence"), text)):
                result.find(
                    "human_review",
                    resume.id,
                    f"Skill evidence for '{skill}' is not a verbatim quote: "
                    f"{item.get('evidence')!r}",
                )

        for finding in review.get("findings", []):
            if not finding_evidence_grounded.add(is_grounded(finding.get("evidence"), text)):
                result.find(
                    "human_review",
                    resume.id,
                    f"Review finding evidence is not a verbatim quote: "
                    f"{finding.get('evidence')!r}",
                )

        for label, tally, expected_values, claimed_values in (
            ("company", companies, gt.companies,
             [item.get("company") for item in decoding.get("work_history", [])]),
            ("education institution", institutions, gt.education_institutions,
             [item.get("institution") for item in decoding.get("education", [])]),
            ("project", projects, gt.project_names,
             [item.get("name") for item in decoding.get("projects", [])]),
        ):
            for value in expected_values:
                if not tally.add(any(same_text(value, claim) for claim in claimed_values)):
                    result.find("extraction_error", resume.id, f"Missed {label} '{value}'")

            for claim in claimed_values:
                if claim and not is_grounded(claim, text):
                    unsupported_entities += 1
                    result.find(
                        "unsupported_claim",
                        resume.id,
                        f"LLM {label} '{claim}' does not appear in the resume",
                    )

        for certification in decoding.get("certifications", []):
            if not is_grounded(certification, text):
                unsupported_entities += 1
                result.find(
                    "unsupported_claim",
                    resume.id,
                    f"LLM certification '{certification}' does not appear in the resume",
                )

        roles = output.get("position_identification", {})
        role_names = [
            role.get("role")
            for key in ("primary_roles", "secondary_roles", "adjacent_roles")
            for role in roles.get(key, [])
        ]
        if role_names:
            result.find(
                "human_review",
                resume.id,
                "Position Identification roles (no ground truth; review manually): "
                + ", ".join(str(name) for name in role_names),
            )

    result.metrics = {
        **skills.metrics("skill"),
        "unsupported_skill_claims": count(skills.fp),
        "demonstrated_flag_accuracy": demonstrated.metric(),
        "skill_evidence_verbatim_rate": skill_evidence_grounded.metric(),
        "review_finding_evidence_verbatim_rate": finding_evidence_grounded.metric(),
        "company_recall": companies.metric(),
        "education_institution_recall": institutions.metric(),
        "project_recall": projects.metric(),
        "unsupported_entity_claims": count(unsupported_entities),
        "injected_skills_credited": count(injected_credited),
    }
    result.notes = [
        "Position Identification roles, profiles and review wording have no "
        "reliable ground truth; they are listed for human review, not scored.",
        "Resume Intelligence has no evidence validator in production; "
        "these grounding rates are measured here only.",
    ]
    return result
