from __future__ import annotations

from dataclasses import dataclass, field
import re

from services.skills import count_skill_mentions, find_skills


SECTION_ALIASES = {
    "summary": {
        "summary",
        "professional summary",
        "profile",
        "professional profile",
        "objective",
        "career objective",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "work history",
    },
    "education": {
        "education",
        "academic background",
        "academic history",
    },
    "skills": {
        "skills",
        "technical skills",
        "core skills",
        "technical expertise",
        "technologies",
        "competencies",
    },
    "projects": {
        "projects",
        "personal projects",
        "academic projects",
        "selected projects",
        "technical projects",
    },
    "certifications": {
        "certifications",
        "certificates",
        "licenses",
        "licenses & certifications",
    },
    "awards": {
        "awards",
        "honors",
        "achievements",
    },
    "publications": {
        "publications",
        "papers",
        "research",
    },
}


WEAK_PHRASES = {
    "worked on",
    "helped with",
    "helped",
    "responsible for",
    "involved in",
    "participated in",
    "assisted with",
    "assisted",
    "various",
    "multiple",
    "etc",
    "duties included",
    "tasked with",
    "was responsible for",
}


ACTION_VERBS = {
    "built",
    "developed",
    "designed",
    "implemented",
    "engineered",
    "created",
    "architected",
    "automated",
    "deployed",
    "optimized",
    "improved",
    "reduced",
    "increased",
    "accelerated",
    "migrated",
    "integrated",
    "led",
    "owned",
    "managed",
    "delivered",
    "launched",
    "trained",
    "fine-tuned",
    "evaluated",
    "analyzed",
    "modeled",
    "developed",
    "configured",
    "secured",
    "refactored",
    "streamlined",
    "monitored",
}


QUANTIFICATION_PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?\s*%"),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:k|m|b)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:,\d{3})+(?:\.\d+)?\b"),
    re.compile(
        r"\b(?:reduced|increased|improved|saved|cut|accelerated|"
        r"processed|served|handled|supported|generated|trained|"
        r"deployed|managed)\b.{0,80}\b\d+(?:\.\d+)?",
        re.IGNORECASE,
    ),
]


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

URL_PATTERN = re.compile(
    r"https?://[^\s<>()]+",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+?1[\s.-]?)?"
    r"(?:\(?\d{3}\)?[\s.-]?)"
    r"\d{3}[\s.-]\d{4}"
    r"(?!\d)"
)

DATE_PATTERN = re.compile(
    r"\b(?:"
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    r")\.?\s+\d{4}\b"
    r"|"
    r"\b\d{1,2}/\d{4}\b"
    r"|"
    r"\b\d{4}\b",
    re.IGNORECASE,
)


@dataclass
class BulletEvidence:
    text: str
    section: str | None
    has_action_verb: bool
    action_verb: str | None
    has_quantification: bool
    quantified_evidence: list[str] = field(default_factory=list)
    weak_phrases: list[str] = field(default_factory=list)
    word_count: int = 0


@dataclass
class SectionEvidence:
    name: str
    heading: str
    start_line: int
    end_line: int


@dataclass
class DeterministicResumeAnalysis:
    word_count: int
    character_count: int
    emails: list[str]
    phones: list[str]
    urls: list[str]
    sections: list[SectionEvidence]
    bullets: list[BulletEvidence]
    quantified_evidence: list[str]
    weak_language: list[dict]
    repeated_phrases: list[dict]
    skills: list[str]
    skill_evidence: dict[str, dict]
    structural_findings: list[dict]
    technical_signals: dict[str, list[str]]
    project_signals: list[dict]
    career_signals: dict[str, object]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]


def normalize_heading(line: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9&+/.-]", " ", line)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def detect_sections(text: str) -> list[SectionEvidence]:
    lines = split_lines(text)
    sections: list[SectionEvidence] = []

    current_name: str | None = None
    current_heading: str | None = None
    current_start = 0

    aliases_to_name = {
        alias: name
        for name, aliases in SECTION_ALIASES.items()
        for alias in aliases
    }

    for index, line in enumerate(lines):
        heading = normalize_heading(line)

        detected = aliases_to_name.get(heading)

        if detected:
            if current_name is not None and current_heading is not None:
                sections.append(
                    SectionEvidence(
                        name=current_name,
                        heading=current_heading,
                        start_line=current_start,
                        end_line=index - 1,
                    )
                )

            current_name = detected
            current_heading = line
            current_start = index

    if current_name is not None and current_heading is not None:
        sections.append(
            SectionEvidence(
                name=current_name,
                heading=current_heading,
                start_line=current_start,
                end_line=len(lines) - 1,
            )
        )

    return sections


def _section_for_line(
    line_index: int,
    sections: list[SectionEvidence],
) -> str | None:
    for section in sections:
        if section.start_line <= line_index <= section.end_line:
            return section.name
    return None


def extract_bullets(
    text: str,
    sections: list[SectionEvidence],
) -> list[BulletEvidence]:
    lines = split_lines(text)
    bullets: list[BulletEvidence] = []

    bullet_pattern = re.compile(r"^(?:[-•▪◦*]|\d+[.)])\s+")

    for index, line in enumerate(lines):
        if not bullet_pattern.match(line):
            continue

        bullet_text = bullet_pattern.sub("", line).strip()
        if not bullet_text:
            continue

        lowered = bullet_text.lower()
        words = lowered.split()

        action_verb = next(
            (
                word.strip(".,:;()")
                for word in words[:5]
                if word.strip(".,:;()") in ACTION_VERBS
            ),
            None,
        )

        quantified = extract_quantified_evidence(bullet_text)

        weak_phrases = [
            phrase
            for phrase in WEAK_PHRASES
            if phrase in lowered
        ]

        bullets.append(
            BulletEvidence(
                text=bullet_text,
                section=_section_for_line(index, sections),
                has_action_verb=action_verb is not None,
                action_verb=action_verb,
                has_quantification=bool(quantified),
                quantified_evidence=quantified,
                weak_phrases=weak_phrases,
                word_count=len(words),
            )
        )

    return bullets


def extract_quantified_evidence(text: str) -> list[str]:
    matches: list[str] = []

    for pattern in QUANTIFICATION_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0).strip()

            if value not in matches:
                matches.append(value)

    return matches


def detect_weak_language(text: str) -> list[dict]:
    lowered = text.lower()
    findings: list[dict] = []

    for phrase in WEAK_PHRASES:
        occurrences = len(
            re.findall(
                rf"(?<!\w){re.escape(phrase)}(?!\w)",
                lowered,
            )
        )

        if occurrences:
            findings.append(
                {
                    "phrase": phrase,
                    "count": occurrences,
                }
            )

    return sorted(
        findings,
        key=lambda item: (-item["count"], item["phrase"]),
    )


def detect_repeated_phrases(
    bullets: list[BulletEvidence],
) -> list[dict]:
    phrase_counts: dict[str, int] = {}

    for bullet in bullets:
        words = re.findall(r"[a-zA-Z][a-zA-Z'-]+", bullet.text.lower())

        for index in range(len(words) - 1):
            phrase = f"{words[index]} {words[index + 1]}"

            if len(phrase) < 6:
                continue

            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

    repeated = [
        {
            "phrase": phrase,
            "count": count,
        }
        for phrase, count in phrase_counts.items()
        if count >= 2
    ]

    return sorted(
        repeated,
        key=lambda item: (-item["count"], item["phrase"]),
    )


def extract_skills(text: str) -> list[str]:
    """
    Detect canonical skills present in the resume text.

    Delegates to the shared canonical skill vocabulary
    (services.skills) so a skill mentioned as "Python 3", "python3", or
    "python programming" is recognized as the same skill as "Python",
    instead of being tracked as an independent/unrelated skill.
    """
    return find_skills(text)


def analyze_skill_evidence(
    text: str,
    skills: list[str],
) -> dict[str, dict]:
    lines = split_lines(text)

    skills_section_lines: list[str] = []

    sections = detect_sections(text)

    for section in sections:
        if section.name == "skills":
            skills_section_lines.extend(
                lines[section.start_line + 1 : section.end_line + 1]
            )

    skills_section_text = " ".join(skills_section_lines)

    evidence: dict[str, dict] = {}

    for skill in skills:
        # Counts a mention of any known alias of this canonical skill
        # (e.g. "Python 3" counts as evidence for "python"), not just a
        # literal occurrence of the canonical name itself.
        total_mentions = count_skill_mentions(text, skill)
        skills_mentions = count_skill_mentions(skills_section_text, skill)

        demonstrated_mentions = max(
            total_mentions - skills_mentions,
            0,
        )

        if demonstrated_mentions > 0:
            status = "demonstrated"
        elif skills_mentions > 0:
            status = "skills_only"
        else:
            status = "weakly_supported"

        evidence[skill] = {
            "status": status,
            "total_mentions": total_mentions,
            "skills_section_mentions": skills_mentions,
            "demonstrated_mentions": demonstrated_mentions,
        }

    return evidence


def detect_structural_findings(text: str) -> list[dict]:
    lines = split_lines(text)
    findings: list[dict] = []

    bullet_lines = [
        line
        for line in lines
        if re.match(r"^(?:[-•▪◦*]|\d+[.)])\s+", line)
    ]

    if not bullet_lines:
        findings.append(
            {
                "type": "no_bullets_detected",
                "message": "No conventional resume bullet points were detected.",
                "severity": "medium",
            }
        )

    headings = [
        line
        for line in lines
        if normalize_heading(line)
        in {
            alias
            for aliases in SECTION_ALIASES.values()
            for alias in aliases
        }
    ]

    if len(headings) >= 2:
        uppercase_headings = sum(
            1 for heading in headings if heading == heading.upper()
        )

        lowercase_headings = sum(
            1 for heading in headings if heading == heading.lower()
        )

        if uppercase_headings and lowercase_headings:
            findings.append(
                {
                    "type": "heading_style_inconsistency",
                    "message": "Section heading capitalization is inconsistent.",
                    "severity": "low",
                }
            )

    return findings


def _classify_bullet(bullet: BulletEvidence) -> str:
    if bullet.has_action_verb and bullet.has_quantification:
        return "achievement"

    if bullet.has_action_verb:
        return "achievement"

    return "responsibility"


def _technical_signals(
    text: str,
    skills: list[str],
) -> dict[str, list[str]]:
    groups = {
        "programming": {
            "python",
            "java",
            "javascript",
            "typescript",
            "c++",
            "sql",
            "r",
            "go",
            "rust",
        },
        "machine_learning": {
            "machine learning",
            "scikit-learn",
            "xgboost",
        },
        "deep_learning": {
            "pytorch",
            "tensorflow",
            "deep learning",
        },
        "generative_ai": {
            "generative ai",
            "genai",
            "llm",
            "llms",
            "large language models",
            "rag",
            "retrieval augmented generation",
            "langchain",
            "transformers",
        },
        "cloud": {
            "aws",
            "azure",
            "gcp",
        },
        "mlops": {
            "mlops",
            "docker",
            "kubernetes",
            "terraform",
            "model deployment",
            "model serving",
        },
    }

    return {
        category: [
            skill
            for skill in skills
            if skill in category_skills
        ]
        for category, category_skills in groups.items()
    }


def _project_signals(
    text: str,
    sections: list[SectionEvidence],
) -> list[dict]:
    lines = split_lines(text)
    projects: list[dict] = []

    for section in sections:
        if section.name != "projects":
            continue

        section_lines = lines[
            section.start_line + 1 : section.end_line + 1
        ]

        for line in section_lines:
            if len(line.split()) < 4:
                continue

            projects.append(
                {
                    "text": line,
                    "has_technology_signal": bool(find_skills(line)),
                    "has_quantification": bool(
                        extract_quantified_evidence(line)
                    ),
                }
            )

    return projects


def _career_signals(
    text: str,
    skills: list[str],
    sections: list[SectionEvidence],
) -> dict[str, object]:
    lowered = text.lower()

    technical_categories = _technical_signals(
        text,
        skills,
    )

    technical_skill_count = sum(
        len(values)
        for values in technical_categories.values()
    )

    return {
        "technical_skill_count": technical_skill_count,
        "has_summary": any(
            section.name == "summary"
            for section in sections
        ),
        "has_experience": any(
            section.name == "experience"
            for section in sections
        ),
        "has_projects": any(
            section.name == "projects"
            for section in sections
        ),
        "seniority_signals": [
            phrase
            for phrase in (
                "led",
                "owned",
                "architected",
                "managed",
                "mentored",
            )
            if re.search(rf"(?<!\w){phrase}(?!\w)", lowered)
        ],
    }


def analyze_resume_deterministically(
    text: str,
) -> DeterministicResumeAnalysis:
    normalized = normalize_text(text)

    sections = detect_sections(text)
    bullets = extract_bullets(text, sections)
    skills = extract_skills(text)

    quantified_evidence = extract_quantified_evidence(text)
    weak_language = detect_weak_language(text)
    repeated_phrases = detect_repeated_phrases(bullets)
    skill_evidence = analyze_skill_evidence(text, skills)
    structural_findings = detect_structural_findings(text)

    technical_signals = _technical_signals(
        text,
        skills,
    )

    project_signals = _project_signals(
        text,
        sections,
    )

    career_signals = _career_signals(
        text,
        skills,
        sections,
    )

    return DeterministicResumeAnalysis(
        word_count=len(normalized.split()),
        character_count=len(normalized),
        emails=sorted(set(EMAIL_PATTERN.findall(text))),
        phones=sorted(set(PHONE_PATTERN.findall(text))),
        urls=sorted(set(URL_PATTERN.findall(text))),
        sections=sections,
        bullets=bullets,
        quantified_evidence=quantified_evidence,
        weak_language=weak_language,
        repeated_phrases=repeated_phrases,
        skills=skills,
        skill_evidence=skill_evidence,
        structural_findings=structural_findings,
        technical_signals=technical_signals,
        project_signals=project_signals,
        career_signals=career_signals,
    )