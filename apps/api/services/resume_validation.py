from __future__ import annotations

from dataclasses import dataclass, field
import re


MIN_RESUME_CHARACTERS = 300
MIN_RESUME_WORDS = 50

RECOGNIZABLE_SECTIONS = {
    "summary": {
        "summary",
        "professional summary",
        "profile",
        "professional profile",
        "objective",
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
}


@dataclass(frozen=True)
class ResumeValidationResult:
    valid: bool
    warnings: list[str] = field(default_factory=list)
    word_count: int = 0
    character_count: int = 0
    section_matches: list[str] = field(default_factory=list)


def _normalize_heading(line: str) -> str:
    heading = re.sub(r"[^a-zA-Z0-9&+/.-]", " ", line)
    return re.sub(r"\s+", " ", heading).strip().lower()


def validate_resume_text(text: str) -> ResumeValidationResult:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    word_count = len(normalized.split())
    character_count = len(normalized)

    section_names = {
        section_name
        for section_name, aliases in RECOGNIZABLE_SECTIONS.items()
        if any(
            _normalize_heading(line) in aliases
            for line in (text or "").splitlines()
        )
    }
    section_matches = sorted(section_names)

    warnings: list[str] = []
    if character_count < MIN_RESUME_CHARACTERS:
        warnings.append(
            f"Resume text must contain at least {MIN_RESUME_CHARACTERS} characters."
        )
    if word_count < MIN_RESUME_WORDS:
        warnings.append(
            f"Resume text must contain at least {MIN_RESUME_WORDS} words."
        )
    if not section_matches:
        warnings.append("No recognizable resume sections were found.")

    return ResumeValidationResult(
        valid=not warnings,
        warnings=warnings,
        word_count=word_count,
        character_count=character_count,
        section_matches=section_matches,
    )