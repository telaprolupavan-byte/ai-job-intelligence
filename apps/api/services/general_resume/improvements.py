"""Resume-level improvement detection (AJI-027): pure and deterministic.

Every improvement is derived from a signal the existing deterministic
analyzer already produces (see `scoring.py`); nothing here adds a
detection rule, reads a job, or calls an AI provider. The AI stage (see
`validator.py`) may later replace an improvement's `explanation` and
`guidance` text, but never adds, removes, or re-types an improvement.

Stable identity: `improvement_id` is a hash of the improvement's kind and
the normalized text (or target) it is anchored to. An unchanged line in
a child version therefore keeps the same id as in its parent, which is
what lets a rejection carry forward while "the underlying unchanged
issue remains" - and what lets a changed line count as resolved.

Grouping: all issues detected on one bullet are one improvement, so two
approvals can never compete to rewrite the same line. Identical bullet
lines share one id (and one replacement).
"""

from __future__ import annotations

import hashlib
import re

from apps.api.services.general_resume.contracts import Improvement
from apps.api.services.general_resume.scoring import (
    CORE_SECTIONS,
    IMPACT_SECTIONS,
    structure_checks,
)
from apps.api.services.resume_ai.deterministic import (
    DeterministicResumeAnalysis,
    split_lines,
)
from services.skills import count_skill_mentions


ANALYZER_VERSION = "1.0"

# The same marker pattern `resume_ai.deterministic.extract_bullets` uses,
# needed here to recover each bullet's exact source line (the analyzer
# stores bullet text without its marker).
BULLET_PATTERN = re.compile(r"^(?:[-•▪◦*]|\d+[.)])\s+")

SECTION_TITLES = {
    "experience": "Experience",
    "education": "Education",
    "skills": "Skills",
}

_ISSUE_TITLES = {
    "weak_phrase": "weak phrasing",
    "no_action_verb": "no leading action verb",
    "no_quantification": "no measurable result",
}

_ISSUE_COMPONENTS = {
    "weak_phrase": "clarity",
    "no_action_verb": "action_writing",
    "no_quantification": "measurable_impact",
}


def normalize_anchor(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def improvement_id(kind: str, key: str) -> str:
    digest = hashlib.sha256(f"{kind}:{normalize_anchor(key)}".encode("utf-8"))
    return digest.hexdigest()[:24]


def _bullet_lines(text: str) -> list[str]:
    """Stripped source lines that the analyzer treats as bullets, in the
    same order as `DeterministicResumeAnalysis.bullets`."""
    lines = []

    for line in split_lines(text):
        if not BULLET_PATTERN.match(line):
            continue

        if not BULLET_PATTERN.sub("", line).strip():
            continue

        lines.append(line)

    return lines


def _bullet_improvement(bullet, anchor_line: str) -> Improvement | None:
    issues: list[str] = []

    if bullet.weak_phrases:
        issues.append("weak_phrase")

    if not bullet.has_action_verb:
        issues.append("no_action_verb")

    if bullet.section in IMPACT_SECTIONS and not bullet.has_quantification:
        issues.append("no_quantification")

    if not issues:
        return None

    suggestion_type = (
        "ADD_IF_TRUE" if "no_quantification" in issues else "REPHRASE_EXISTING"
    )

    explanation_parts = []

    if "weak_phrase" in issues:
        phrases = ", ".join(f'"{phrase}"' for phrase in sorted(bullet.weak_phrases))
        explanation_parts.append(
            f"This bullet uses weak phrasing ({phrases}), which describes "
            "involvement rather than what you did."
        )

    if "no_action_verb" in issues:
        explanation_parts.append(
            "It does not open with an action verb, so the reader has to "
            "work out what your contribution was."
        )

    if "no_quantification" in issues:
        explanation_parts.append(
            "It does not state a measurable result, so its impact is "
            "hard to judge."
        )

    if suggestion_type == "ADD_IF_TRUE":
        guidance = (
            "Rewrite this bullet in your own words, leading with what you "
            "did. Only if you know a real, accurate result for this work "
            "(a number, percentage or scale), include it. Never add a "
            "figure you cannot stand behind."
        )
    else:
        guidance = (
            "Rewrite this bullet in your own words, leading with what you "
            "did and dropping filler phrases. Keep every fact as it is."
        )

    return Improvement(
        improvement_id=improvement_id("bullet", anchor_line),
        kind="bullet",
        suggestion_type=suggestion_type,
        components=sorted({_ISSUE_COMPONENTS[issue] for issue in issues}),
        issues=issues,
        title="Bullet with " + ", ".join(_ISSUE_TITLES[i] for i in issues),
        evidence=bullet.text,
        anchor_line=anchor_line,
        explanation=" ".join(explanation_parts),
        guidance=guidance,
    )


def _skills_section_line(
    text: str,
    analysis: DeterministicResumeAnalysis,
    skill: str,
) -> str | None:
    lines = split_lines(text)

    for section in analysis.sections:
        if section.name != "skills":
            continue

        for line in lines[section.start_line + 1 : section.end_line + 1]:
            if count_skill_mentions(line, skill):
                return line

    return None


def detect_improvements(
    text: str,
    analysis: DeterministicResumeAnalysis,
    insufficient_components: set[str],
) -> list[Improvement]:
    """Every improvement for one resume's text, in a stable order."""
    checks = structure_checks(analysis)
    improvements: list[Improvement] = []

    for contact, present in (
        ("email", checks.has_email),
        ("phone", checks.has_phone),
    ):
        if present:
            continue

        improvements.append(
            Improvement(
                improvement_id=improvement_id("missing_contact", contact),
                kind="missing_contact",
                suggestion_type="ADD_IF_TRUE",
                components=["structure"],
                title=f"No {'email address' if contact == 'email' else 'phone number'} detected",
                target=contact,
                explanation=(
                    f"No {'email address' if contact == 'email' else 'phone number'} "
                    "was found in the resume text, so a reader may have no "
                    "direct way to contact you."
                ),
                guidance=(
                    f"If you want to be contacted this way, add your "
                    f"{'email address' if contact == 'email' else 'phone number'} "
                    "exactly as it should appear. It is placed under your "
                    "name at the top."
                ),
            )
        )

    section_components = {
        "experience": "measurable_impact",
        "skills": "skill_evidence",
    }

    for section in CORE_SECTIONS:
        if checks.has_sections[section]:
            continue

        components = ["structure"]
        extra = section_components.get(section)

        if extra and extra in insufficient_components:
            components.append(extra)

        title = SECTION_TITLES[section]

        improvements.append(
            Improvement(
                improvement_id=improvement_id("missing_section", section),
                kind="missing_section",
                suggestion_type="ADD_IF_TRUE",
                components=components,
                title=f"No {title} section detected",
                target=section,
                explanation=(
                    f"The resume has no recognizable {title} heading, so "
                    "readers and resume parsers may not find this "
                    "information."
                ),
                guidance=(
                    f"If you have {title.lower()} to list, add it in your "
                    f"own words. It is placed under a \"{title}\" heading. "
                    "If it is already in the resume under another heading, "
                    "you can reject this."
                ),
            )
        )

    if not checks.has_bullets:
        improvements.append(
            Improvement(
                improvement_id=improvement_id("no_bullets", "document"),
                kind="no_bullets",
                suggestion_type="ADVISORY",
                components=[
                    "structure",
                    "action_writing",
                    "measurable_impact",
                    "clarity",
                ],
                title="No bullet points detected",
                explanation=(
                    "No conventional bullet points were detected, so "
                    "action-oriented writing, measurable impact and clarity "
                    "could not be measured."
                ),
                guidance=(
                    "Consider formatting your experience as bullet points "
                    "and uploading the revised document as a new version."
                ),
            )
        )

    if not checks.consistent_headings:
        improvements.append(
            Improvement(
                improvement_id=improvement_id("inconsistent_headings", "document"),
                kind="inconsistent_headings",
                suggestion_type="ADVISORY",
                components=["structure"],
                title="Inconsistent heading capitalization",
                explanation=(
                    "Section headings mix upper-case and lower-case styles."
                ),
                guidance=(
                    "Consider using one heading style throughout, then "
                    "upload the revised document as a new version."
                ),
            )
        )

    bullet_lines = _bullet_lines(text)
    seen: set[str] = set()

    for bullet, anchor_line in zip(analysis.bullets, bullet_lines):
        # Both lists come from the same lines with the same pattern; the
        # check keeps a bullet from ever being anchored to the wrong line.
        if BULLET_PATTERN.sub("", anchor_line).strip() == bullet.text:
            item = _bullet_improvement(bullet, anchor_line)

            if item is None or item.improvement_id in seen:
                continue

            seen.add(item.improvement_id)
            improvements.append(item)

    present_sections = {section.name for section in analysis.sections}

    if (
        "measurable_impact" in insufficient_components
        and checks.has_bullets
        and present_sections & IMPACT_SECTIONS
    ):
        improvements.append(
            Improvement(
                improvement_id=improvement_id("no_impact_bullets", "document"),
                kind="no_impact_bullets",
                suggestion_type="ADVISORY",
                components=["measurable_impact"],
                title="No bullet points in experience or projects",
                explanation=(
                    "Your experience and project sections have no bullet "
                    "points, so measurable impact could not be assessed."
                ),
                guidance=(
                    "Consider describing each role or project as bullet "
                    "points and uploading the revised document as a new "
                    "version."
                ),
            )
        )

    for skill, evidence in sorted(analysis.skill_evidence.items()):
        if evidence.get("status") != "skills_only":
            continue

        improvements.append(
            Improvement(
                improvement_id=improvement_id("skill_not_demonstrated", skill),
                kind="skill_not_demonstrated",
                suggestion_type="ADD_IF_TRUE",
                components=["skill_evidence"],
                title=f"\"{skill}\" appears only in the skills list",
                evidence=_skills_section_line(text, analysis, skill),
                target=skill,
                explanation=(
                    f"\"{skill}\" is listed as a skill but never shown in "
                    "use in your experience or projects."
                ),
                guidance=(
                    f"If you have actually used {skill}, add a line in your "
                    "own words describing where and how. It is placed under "
                    "an experience heading. If not, you can reject this."
                ),
            )
        )

    if (
        "skill_evidence" in insufficient_components
        and checks.has_sections["skills"]
    ):
        improvements.append(
            Improvement(
                improvement_id=improvement_id("no_recognized_skills", "document"),
                kind="no_recognized_skills",
                suggestion_type="ADVISORY",
                components=["skill_evidence"],
                title="No recognized skills detected",
                explanation=(
                    "None of the skills in your resume matched NERO's skill "
                    "vocabulary, so skill evidence could not be measured."
                ),
                guidance=(
                    "Consider naming your skills with their common names. "
                    "You can reject this if your skills are listed as you "
                    "want them."
                ),
            )
        )

    return improvements
