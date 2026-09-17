"""Deterministic Job Intelligence extraction (AJI-012).

Handles everything that can be extracted from a job posting's own
structured fields and explicit text patterns without an LLM: employment
type, location/work arrangement, required-vs-preferred skills
(canonical, via `services.skills`), years-of-experience requirements,
education, certifications, responsibilities, work-authorization signals,
and compensation.

This module never guesses: a field stays `None`/`"unknown"` unless the
job text (or an already-normalized structured field) actually supports
it. It reuses existing extraction building blocks instead of introducing
parallel logic:

- `services.skills` for canonical skill identity (AJI-009).
- `services.job_discovery.normalizer` for employment/remote type alias
  normalization (same aliasing job discovery itself uses).
- `services.job_matching.extractor.PREFERRED_SECTION_MARKERS` for the
  same "preferred qualifications"/"nice to have" section-heading phrases
  job matching already recognizes.
- `services.eligibility.job_signals.extract_work_authorization_signals`
  for the base sponsorship/authorization/citizenship/clearance phrase
  detection (AJI-011), extended here only with the "preferred" nuance
  (citizenship/clearance) that eligibility's boolean signals don't need.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from apps.api.services.job_intelligence.contracts import (
    AuthorizationSignals,
    CertificationRequirement,
    CompensationInfo,
    EducationRequirement,
    EmploymentInfo,
    ExperienceRequirement,
    LocationInfo,
    ResponsibilityItem,
    SkillRequirement,
)
from services.eligibility.job_signals import extract_work_authorization_signals
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
)
from services.job_matching.extractor import PREFERRED_SECTION_MARKERS
from services.skills import find_skills


Level = Literal["required", "preferred"]


def _normalize_token(token: str) -> str:
    """Lowercase and strip punctuation noise for dict-keyed lookups."""
    return re.sub(r"[.']", "", token.strip().lower())


@dataclass
class RawJobDescription:
    """Plain-data view of the job fields this module extracts from.

    Deliberately not the SQLAlchemy `Job` model, so this entire module
    stays a pure function of plain data and is trivial to unit test.
    """

    title: str
    description: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    location: str | None = None
    country: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    contract_duration: str | None = None
    contract_worker_type: str | None = None


@dataclass
class DeterministicExtraction:
    seniority: str | None
    employment: EmploymentInfo
    location: LocationInfo
    required_skills: list[SkillRequirement] = field(default_factory=list)
    preferred_skills: list[SkillRequirement] = field(default_factory=list)
    required_experience: list[ExperienceRequirement] = field(
        default_factory=list
    )
    preferred_experience: list[ExperienceRequirement] = field(
        default_factory=list
    )
    education: list[EducationRequirement] = field(default_factory=list)
    certifications: list[CertificationRequirement] = field(
        default_factory=list
    )
    responsibilities: list[ResponsibilityItem] = field(default_factory=list)
    authorization: AuthorizationSignals = field(
        default_factory=AuthorizationSignals
    )
    compensation: CompensationInfo = field(default_factory=CompensationInfo)


def requirement_text(raw: RawJobDescription) -> str:
    """Text scanned for requirements/skills/experience/education/certs.

    Deliberately excludes `responsibilities` — responsibilities are
    captured separately and must never be treated as requirements (see
    docs/ARCHITECTURE.md and AJI-012 section 7).
    """
    return "\n".join(
        part for part in [raw.description, raw.requirements] if part
    )


# ---------------------------------------------------------------------------
# Required vs. preferred classification
# ---------------------------------------------------------------------------

REQUIRED_MARKERS = (
    "required",
    "require",
    "requires",
    "must have",
    "must-have",
    "must",
    "minimum of",
    "minimum",
    "mandatory",
    "essential",
)

PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "a plus",
    "plus",
    "desired",
    "ideally",
)

_CLAUSE_SPLIT_PATTERN = re.compile(r"[.;\n]+")
_LEADING_BULLET_PATTERN = re.compile(r"^\s*(?:[-•▪◦*]|\d+[.)])\s+")


def split_clauses(text: str) -> list[str]:
    if not text:
        return []

    clauses: list[str] = []

    for raw_clause in _CLAUSE_SPLIT_PATTERN.split(text):
        cleaned = _LEADING_BULLET_PATTERN.sub("", raw_clause).strip()

        if cleaned:
            clauses.append(cleaned)

    return clauses


def classify_level(clause: str, *, default: Level) -> tuple[str, bool]:
    """Classify a clause as required/preferred.

    Returns (level, matched_explicitly). An explicit inline marker
    ("required", "preferred", "nice to have", "bonus", ...) always wins;
    absent that, the clause falls back to the current section-level
    default (see `iter_clauses_with_default_level`).
    """
    lowered = clause.lower()

    if any(marker in lowered for marker in PREFERRED_MARKERS):
        return "preferred", True

    if any(marker in lowered for marker in REQUIRED_MARKERS):
        return "required", True

    return default, False


def iter_clauses_with_default_level(
    text: str,
) -> list[tuple[str, Level]]:
    """
    Clause-split the full text once, tracking a running section-level
    default (required, until a "Preferred Qualifications"/"Nice to
    Have"-style heading clause is seen, after which later clauses default
    to preferred).

    This is deliberately clause-first rather than
    `split_preferred_section`-first: splitting the whole text into a
    must-have half and a preferred half *before* clause-splitting would
    cut an inline sentence like "Kubernetes experience is nice to have"
    in two at the marker, separating the skill from its own marker. A
    pure section-heading clause (the clause text, ignoring a trailing
    colon, exactly matches a marker phrase) updates the running default
    without being emitted as a requirement clause itself.
    """
    default: Level = "required"
    results: list[tuple[str, Level]] = []

    for clause in split_clauses(text):
        heading = clause.strip().rstrip(":").strip().lower()

        if heading in PREFERRED_SECTION_MARKERS:
            default = "preferred"
            continue

        results.append((clause, default))

    return results


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def extract_skill_requirements(
    text: str,
) -> tuple[list[SkillRequirement], list[SkillRequirement]]:
    """
    Detect canonical skills (services.skills) and classify each as
    required/preferred with evidence, never inferring a skill that is not
    explicitly present in the text.
    """
    required: dict[str, SkillRequirement] = {}
    preferred: dict[str, SkillRequirement] = {}

    for clause, default_level in iter_clauses_with_default_level(text):
        skills = find_skills(clause)

        if not skills:
            continue

        level, matched = classify_level(clause, default=default_level)
        confidence = "high" if matched else "medium"
        target = required if level == "required" else preferred

        for skill in skills:
            if skill in target:
                continue

            target[skill] = SkillRequirement(
                canonical_skill=skill,
                level=level,
                evidence_text=clause,
                confidence=confidence,
            )

    # A skill required anywhere in the JD is never also listed as
    # preferred — required always wins, and preferred is never promoted
    # to required.
    for skill in list(preferred.keys()):
        if skill in required:
            del preferred[skill]

    return list(required.values()), list(preferred.values())


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------

_YEARS_PATTERN = re.compile(
    r"(?P<years>\d+(?:\.\d+)?)\+?\s+years?\b",
    re.IGNORECASE,
)

_EXPERIENCE_CONTEXT_KEYWORDS = (
    "production",
    "leadership",
    "management",
    "enterprise",
    "hands-on",
    "hands on",
)


def extract_experience_items(
    text: str,
) -> tuple[list[ExperienceRequirement], list[ExperienceRequirement]]:
    """
    Extract explicit "N years ... experience" requirements only. This
    intentionally never treats an arbitrary number (a founding year, a
    team size, a version number) as years of experience.
    """
    required: list[ExperienceRequirement] = []
    preferred: list[ExperienceRequirement] = []

    for clause, default_level in iter_clauses_with_default_level(text):
        match = _YEARS_PATTERN.search(clause)

        if not match:
            continue

        years = float(match.group("years"))
        level, matched = classify_level(clause, default=default_level)
        confidence = "high" if matched else "medium"

        area_skills = find_skills(clause)
        area = area_skills[0] if area_skills else None

        lowered = clause.lower()
        context = next(
            (
                keyword
                for keyword in _EXPERIENCE_CONTEXT_KEYWORDS
                if keyword in lowered
            ),
            None,
        )

        item = ExperienceRequirement(
            level=level,
            minimum_years=years,
            area=area,
            context=context,
            evidence_text=clause,
            confidence=confidence,
        )

        (required if level == "required" else preferred).append(item)

    return required, preferred


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

_DEGREE_TOKEN_PATTERN = re.compile(
    r"\b(?:BS|B\.S\.|BA|B\.A\.|MS|M\.S\.|MA|M\.A\.|MBA|"
    r"Bachelor'?s?(?:\s+Degree)?|Bachelors?(?:\s+Degree)?|"
    r"Master'?s?(?:\s+Degree)?|Masters?(?:\s+Degree)?|"
    r"Associate'?s?(?:\s+Degree)?|Associates?(?:\s+Degree)?|"
    r"Ph\.?D\.?|Doctorate)\b"
)

_DEGREE_LABELS = {
    "bs": "Bachelor's",
    "ba": "Bachelor's",
    "bachelor": "Bachelor's",
    "bachelors": "Bachelor's",
    "bachelor degree": "Bachelor's",
    "bachelors degree": "Bachelor's",
    "ms": "Master's",
    "ma": "Master's",
    "master": "Master's",
    "masters": "Master's",
    "master degree": "Master's",
    "masters degree": "Master's",
    "mba": "MBA",
    "associate": "Associate's",
    "associates": "Associate's",
    "associate degree": "Associate's",
    "associates degree": "Associate's",
    "phd": "PhD",
    "doctorate": "PhD",
}

_FIELD_AFTER_PATTERN = re.compile(
    r"^\s+in\s+([A-Za-z][A-Za-z&,/ -]{2,60}?)"
    r"(?=[.,;]|\s+(?:is\s+)?(?:required|preferred)\b|$)",
    re.IGNORECASE,
)


def _match_degree(clause: str) -> tuple[str, str | None] | None:
    match = _DEGREE_TOKEN_PATTERN.search(clause)

    if not match:
        return None

    label = _DEGREE_LABELS.get(_normalize_token(match.group(0)))

    if label is None:
        return None

    remainder = clause[match.end():]
    field_match = _FIELD_AFTER_PATTERN.match(remainder)
    field_of_study = field_match.group(1).strip() if field_match else None

    return label, field_of_study


def extract_education_items(
    text: str,
) -> tuple[list[EducationRequirement], list[EducationRequirement]]:
    required: list[EducationRequirement] = []
    preferred: list[EducationRequirement] = []

    for clause, default_level in iter_clauses_with_default_level(text):
        degree = _match_degree(clause)

        if degree is None:
            continue

        degree_level, field_of_study = degree
        level, matched = classify_level(clause, default=default_level)
        confidence = "high" if matched else "medium"

        item = EducationRequirement(
            level=level,
            degree_level=degree_level,
            field_of_study=field_of_study,
            evidence_text=clause,
            confidence=confidence,
        )

        (required if level == "required" else preferred).append(item)

    return required, preferred


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------

_CERTIFICATION_KEYWORDS = (
    "certification",
    "certifications",
    "certified",
    "certificate",
    "certificates",
)


def extract_certification_items(
    text: str,
) -> tuple[list[CertificationRequirement], list[CertificationRequirement]]:
    required: list[CertificationRequirement] = []
    preferred: list[CertificationRequirement] = []

    for clause, default_level in iter_clauses_with_default_level(text):
        lowered = clause.lower()

        if not any(keyword in lowered for keyword in _CERTIFICATION_KEYWORDS):
            continue

        level, matched = classify_level(clause, default=default_level)
        confidence = "high" if matched else "medium"

        item = CertificationRequirement(
            level=level,
            name=clause,
            evidence_text=clause,
            confidence=confidence,
        )

        (required if level == "required" else preferred).append(item)

    return required, preferred


# ---------------------------------------------------------------------------
# Responsibilities (always separate from requirements)
# ---------------------------------------------------------------------------

_BULLET_PATTERN = re.compile(r"^(?:[-•▪◦*]|\d+[.)])\s+")


def extract_responsibilities(text: str | None) -> list[ResponsibilityItem]:
    if not text:
        return []

    items: list[ResponsibilityItem] = []

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()

        if not line:
            continue

        cleaned = _BULLET_PATTERN.sub("", line).strip()

        if not cleaned or len(cleaned.split()) < 3:
            continue

        items.append(
            ResponsibilityItem(description=cleaned, evidence_text=cleaned)
        )

    return items


# ---------------------------------------------------------------------------
# Identity: seniority (title only — never inferred from salary)
# ---------------------------------------------------------------------------

_SENIORITY_KEYWORDS: dict[str, str] = {
    "intern": "Intern",
    "internship": "Intern",
    "entry level": "Entry",
    "entry-level": "Entry",
    "junior": "Junior",
    "jr": "Junior",
    "associate": "Associate",
    "senior": "Senior",
    "sr": "Senior",
    "staff": "Staff",
    "principal": "Principal",
    "lead": "Lead",
    "manager": "Manager",
    "director": "Director",
    "vice president": "VP",
    "vp": "VP",
    "head of": "Head",
    "chief": "Chief",
}

_SENIORITY_PATTERN = re.compile(
    r"(?<![a-z0-9])(?:"
    + "|".join(
        re.escape(keyword)
        for keyword in sorted(
            _SENIORITY_KEYWORDS, key=len, reverse=True
        )
    )
    + r")(?![a-z0-9])",
    re.IGNORECASE,
)


def extract_seniority_from_title(title: str) -> str | None:
    if not title:
        return None

    match = _SENIORITY_PATTERN.search(title)

    if not match:
        return None

    return _SENIORITY_KEYWORDS[_normalize_token(match.group(0))]


# ---------------------------------------------------------------------------
# Employment type
# ---------------------------------------------------------------------------

_CONTRACT_TO_HIRE_PATTERN = re.compile(
    r"contract[\s-]+to[\s-]+hire|contract-to-hire|c2h\b", re.IGNORECASE
)


def extract_employment_info(
    raw: RawJobDescription,
) -> EmploymentInfo:
    combined = f"{raw.employment_type or ''} {requirement_text(raw)}"
    contract_to_hire_match = _CONTRACT_TO_HIRE_PATTERN.search(combined)

    if contract_to_hire_match:
        return EmploymentInfo(
            employment_type="contract_to_hire",
            evidence_text=contract_to_hire_match.group(0),
        )

    normalized = normalize_employment_type(raw.employment_type)

    if normalized:
        return EmploymentInfo(
            employment_type=normalized,
            evidence_text=raw.employment_type,
        )

    return EmploymentInfo(employment_type="unknown", evidence_text=None)


# ---------------------------------------------------------------------------
# Location / work arrangement
# ---------------------------------------------------------------------------

_CITY_STATE_PATTERN = re.compile(
    r"^\s*([A-Za-z .'-]+?)\s*,\s*([A-Z]{2})\s*$"
)

_RELOCATION_PATTERN = re.compile(
    r"relocation\s+(?:assistance|package|available)|"
    r"willing\s+to\s+relocate|open\s+to\s+relocation|"
    r"relocation\s+required",
    re.IGNORECASE,
)

_MULTIPLE_LOCATIONS_PATTERN = re.compile(
    r"^multiple\b", re.IGNORECASE
)


def extract_location_info(raw: RawJobDescription) -> LocationInfo:
    raw_location = raw.location.strip() if raw.location else None

    remote_type = normalize_remote_type(raw.remote_type) or "unknown"
    work_arrangement_text: str | None = None
    location_remainder = raw_location

    if raw_location:
        # A raw location like "Hybrid - Newark, NJ" or "Remote - United
        # States" carries the work arrangement as a prefix.
        prefix_match = re.match(
            r"^\s*(remote|hybrid|on-?site)\s*[-:]\s*(.*)$",
            raw_location,
            re.IGNORECASE,
        )

        if prefix_match:
            work_arrangement_text = raw_location
            inferred = normalize_remote_type(prefix_match.group(1))

            if remote_type == "unknown" and inferred:
                remote_type = inferred

            location_remainder = prefix_match.group(2).strip() or None
        elif remote_type != "unknown":
            work_arrangement_text = raw_location

    city: str | None = None
    state: str | None = None
    additional_locations: list[str] = []

    if location_remainder and not _MULTIPLE_LOCATIONS_PATTERN.search(
        location_remainder
    ):
        parts = [
            part.strip()
            for part in re.split(r"\s*/\s*|\s*;\s*", location_remainder)
            if part.strip()
        ]

        if parts:
            match = _CITY_STATE_PATTERN.match(parts[0])

            if match:
                city = match.group(1).strip()
                state = match.group(2).strip()

            additional_locations = parts[1:]

    relocation_match = _RELOCATION_PATTERN.search(requirement_text(raw))

    return LocationInfo(
        raw_location=raw_location,
        city=city,
        state=state,
        country=raw.country,
        additional_locations=additional_locations,
        remote_type=remote_type,
        work_arrangement_text=work_arrangement_text,
        relocation_mentioned=bool(relocation_match),
        relocation_evidence=(
            relocation_match.group(0) if relocation_match else None
        ),
    )


# ---------------------------------------------------------------------------
# Compensation
# ---------------------------------------------------------------------------

_HOURLY_PATTERN = re.compile(
    r"\$?\d+(?:\.\d+)?\s*(?:/|per)\s*hour", re.IGNORECASE
)


def extract_compensation_info(raw: RawJobDescription) -> CompensationInfo:
    text = requirement_text(raw)

    period: str = "unknown"

    if raw.contract_worker_type and "hour" in raw.contract_worker_type.lower():
        period = "hourly"
    elif _HOURLY_PATTERN.search(text):
        period = "hourly"
    elif raw.salary_min is not None or raw.salary_max is not None:
        period = "annual"

    evidence_text: str | None = None

    if raw.salary_min is not None or raw.salary_max is not None:
        currency = raw.salary_currency or "USD"

        if raw.salary_min is not None and raw.salary_max is not None:
            evidence_text = f"{currency} {raw.salary_min:g}-{raw.salary_max:g}"
        elif raw.salary_min is not None:
            evidence_text = f"{currency} {raw.salary_min:g}+"
        else:
            evidence_text = f"Up to {currency} {raw.salary_max:g}"

    return CompensationInfo(
        salary_min=raw.salary_min,
        salary_max=raw.salary_max,
        currency=raw.salary_currency,
        period=period,
        evidence_text=evidence_text,
    )


# ---------------------------------------------------------------------------
# Authorization (extends AJI-011's job_signals with the "preferred" nuance)
# ---------------------------------------------------------------------------

_CITIZENSHIP_PREFERRED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"citizenship\s+(?:is\s+)?preferred",
        r"(?:u\.?s\.?|united states)\s+citizens?\s+preferred",
    ]
]

_CLEARANCE_PREFERRED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"(?:security\s+)?clearance\s+(?:is\s+)?(?:preferred|a\s+plus|"
        r"nice\s+to\s+have)",
    ]
]

_SPONSORSHIP_REQUIRED_PATTERN = re.compile(
    r"sponsorship\s+(?:is\s+)?required", re.IGNORECASE
)


def extract_authorization_signals(raw: RawJobDescription) -> AuthorizationSignals:
    text = requirement_text(raw)
    signals = extract_work_authorization_signals(text)

    evidence: list[str] = []

    sponsorship_required_match = _SPONSORSHIP_REQUIRED_PATTERN.search(text)

    if signals.sponsorship_available is True:
        sponsorship = "available"
    elif signals.sponsorship_available is False:
        sponsorship = "unavailable"
    elif sponsorship_required_match:
        sponsorship = "required"
        evidence.append(sponsorship_required_match.group(0))
    else:
        sponsorship = "unknown"

    citizenship_preferred_match = next(
        (
            pattern.search(text)
            for pattern in _CITIZENSHIP_PREFERRED_PATTERNS
            if pattern.search(text)
        ),
        None,
    )

    if citizenship_preferred_match:
        citizenship = "preferred"
        evidence.append(citizenship_preferred_match.group(0))
    elif signals.citizenship_required:
        citizenship = "required"
    else:
        citizenship = "unknown"

    clearance_preferred_match = next(
        (
            pattern.search(text)
            for pattern in _CLEARANCE_PREFERRED_PATTERNS
            if pattern.search(text)
        ),
        None,
    )

    if clearance_preferred_match:
        clearance = "preferred"
        evidence.append(clearance_preferred_match.group(0))
    elif signals.clearance_required:
        clearance = "required"
    else:
        clearance = "unknown"

    if signals.authorization_required:
        work_authorization = "explicit_requirement"
    elif signals.sponsorship_available is False:
        work_authorization = "explicit_restriction"
    else:
        work_authorization = "unknown"

    return AuthorizationSignals(
        sponsorship=sponsorship,
        citizenship=citizenship,
        clearance=clearance,
        work_authorization=work_authorization,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def extract_deterministic(raw: RawJobDescription) -> DeterministicExtraction:
    text = requirement_text(raw)

    required_skills, preferred_skills = extract_skill_requirements(text)
    required_experience, preferred_experience = extract_experience_items(text)
    education_required, education_preferred = extract_education_items(text)
    certs_required, certs_preferred = extract_certification_items(text)

    return DeterministicExtraction(
        seniority=extract_seniority_from_title(raw.title),
        employment=extract_employment_info(raw),
        location=extract_location_info(raw),
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        required_experience=required_experience,
        preferred_experience=preferred_experience,
        education=education_required + education_preferred,
        certifications=certs_required + certs_preferred,
        responsibilities=extract_responsibilities(raw.responsibilities),
        authorization=extract_authorization_signals(raw),
        compensation=extract_compensation_info(raw),
    )
