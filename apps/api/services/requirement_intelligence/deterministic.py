"""Deterministic Requirement Intelligence extraction (AJI-020A).

Mirrors `apps.api.services.job_intelligence.deterministic`'s shape
(clause-first splitting, explicit-marker-over-default classification,
never-guess semantics) but produces the richer, item-based
`RequirementIntelligenceResult` model: four-tier importance, explicit
hard-requirement flags, AND/OR/MIN_COUNT/EQUIVALENT relationships,
character-offset provenance, screening constraints kept separate from
scored requirements, and duplicate/contradiction/ambiguity diagnostics.

Reuses existing building blocks rather than introducing parallel logic:
`services.skills` for canonical skill identity (AJI-009, wrapped by
`find_protected_skills` below for related-but-different-technology
protection), `services.job_matching.extractor.PREFERRED_SECTION_MARKERS`
for section-heading phrases, and
`services.eligibility.job_signals.extract_work_authorization_signals` for
the base sponsorship/citizenship/clearance/authorization phrase
detection this module's screening-constraint extraction extends.

This module never guesses: a field stays `None`/absent unless the JD
text actually supports it, and every extracted item keeps a provenance
span pointing back into the exact raw text it was given.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from apps.api.services.requirement_intelligence.contracts import (
    Contradiction,
    DuplicateGroup,
    EducationConstraint,
    CertificationConstraint,
    ExperienceConstraint,
    PromptInjectionSignal,
    RequirementGroup,
    RequirementItem,
    ScreeningConstraint,
)
from services.eligibility.job_signals import extract_work_authorization_signals
from services.job_matching.extractor import PREFERRED_SECTION_MARKERS
from services.skills import find_skills


Tier = Literal["required", "preferred", "contextual", "informational"]

_IMPORTANCE_RANK: dict[str, int] = {
    "required": 3,
    "preferred": 2,
    "contextual": 1,
    "informational": 0,
}


def _normalize_token(token: str) -> str:
    return re.sub(r"[.']", "", token.strip().lower())


def _normalize_for_comparison(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class RawRequirementSource:
    """Plain-data view of the JD fields this module extracts from.

    Deliberately not the SQLAlchemy `Job` model (this module has no DB
    dependency at all — see service.py), so it stays a pure function of
    plain data and is trivial to unit test.
    """

    title: str
    description: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None


def requirement_text(raw: RawRequirementSource) -> str:
    """Text scanned for requirements/skills/experience/education/certs.

    Deliberately excludes `responsibilities` — see
    `extract_responsibility_items`, which scans it separately (mirrors
    AJI-012's "responsibilities vs. requirements" rule).
    """
    return "\n".join(
        part for part in [raw.description, raw.requirements] if part
    )


def full_source_text(raw: RawRequirementSource) -> str:
    """The exact concatenated text provenance spans are offsets into."""
    return "\n".join(
        part
        for part in [raw.description, raw.requirements, raw.responsibilities]
        if part
    )


class IdAllocator:
    """Deterministic, monotonically-increasing id generator.

    Given a fixed input JD and a fixed, deterministic processing order
    (which every extraction pass in this module follows), the same JD
    always produces the same ids — required for idempotent
    re-extraction of unchanged content.
    """

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._counter = 0

    def next(self) -> str:
        self._counter += 1
        return f"{self._prefix}-{self._counter:04d}"


# ---------------------------------------------------------------------------
# Related-but-different technology protection
# ---------------------------------------------------------------------------

# Canonical skill -> compound phrases that name a genuinely different
# technology and must never be counted as a mention of the canonical
# skill itself (e.g. "React Native" is a distinct, mobile-specific
# technology from web "React" — services.skills has no entry for it, and
# this module must not fabricate one by mis-attributing it to "react").
_PROTECTED_COMPOUND_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    "react": ("react native",),
    "node.js": ("node-red",),
    "spark": ("sparkpost", "spark ar"),
    "go": ("go live", "go to market"),
}


def find_protected_skills(text: str) -> list[str]:
    """Like `services.skills.find_skills`, but drops a canonical skill
    when every one of its matches in `text` is actually part of a
    different, protected compound technology name.

    Conservative by construction: after stripping known compound-phrase
    occurrences from the text, the canonical skill is kept only if it is
    still independently detectable in what remains — so a clause
    mentioning both ("React and React Native") still credits "react",
    while a clause mentioning only the compound ("React Native
    experience") never does.
    """
    if not text:
        return []

    candidates = find_skills(text)
    protected: list[str] = []

    for skill in candidates:
        compounds = _PROTECTED_COMPOUND_EXCLUSIONS.get(skill)

        if not compounds:
            protected.append(skill)
            continue

        remainder = text

        for compound in compounds:
            remainder = re.sub(
                re.escape(compound), " ", remainder, flags=re.IGNORECASE
            )

        if skill in find_skills(remainder):
            protected.append(skill)

    return protected


# ---------------------------------------------------------------------------
# Clause splitting with provenance spans
# ---------------------------------------------------------------------------

@dataclass
class ClauseSpan:
    text: str
    start: int
    end: int


_CLAUSE_TOKEN_PATTERN = re.compile(r"[^.;\n]+")
_LEADING_BULLET_PATTERN = re.compile(r"^\s*(?:[-•▪◦*]|\d+[.)])\s+")


def split_clauses_with_spans(text: str) -> list[ClauseSpan]:
    """Clause-split `text`, keeping each clause's exact character offsets
    into `text` (after bullet/whitespace trimming) so every requirement
    extracted from it can carry verifiable provenance."""
    if not text:
        return []

    clauses: list[ClauseSpan] = []

    for match in _CLAUSE_TOKEN_PATTERN.finditer(text):
        raw_clause = match.group(0)
        base = match.start()

        bullet_match = _LEADING_BULLET_PATTERN.match(raw_clause)
        offset = bullet_match.end() if bullet_match else 0
        stripped = raw_clause[offset:]

        lstripped = stripped.lstrip()
        lstrip_len = len(stripped) - len(lstripped)
        cleaned = lstripped.rstrip()

        if not cleaned:
            continue

        start = base + offset + lstrip_len
        clauses.append(ClauseSpan(text=cleaned, start=start, end=start + len(cleaned)))

    return clauses


# ---------------------------------------------------------------------------
# Importance classification (four tiers)
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

HARD_REQUIREMENT_MARKERS = (
    "must have",
    "must-have",
    "mandatory",
    "non-negotiable",
    "hard requirement",
    "will not be considered",
    "minimum qualification",
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

CONTEXTUAL_MARKERS = (
    "our stack",
    "our tech stack",
    "we use",
    "our team uses",
    "built with",
    "built using",
    "powered by",
    "technologies used include",
    "our backend is",
    "our infrastructure",
)

INFORMATIONAL_SECTION_MARKERS = frozenset(
    {
        "about us",
        "about the company",
        "who we are",
        "what we offer",
        "benefits",
        "perks",
        "company overview",
        "equal opportunity employer",
        "eeo statement",
    }
)

_CLAUSE_HAS_AND = re.compile(r"(?<![a-z0-9])and(?![a-z0-9])", re.IGNORECASE)
_CLAUSE_HAS_OR = re.compile(r"(?<![a-z0-9])or(?![a-z0-9])", re.IGNORECASE)


def classify_tier(clause: str, *, default: Tier) -> tuple[Tier, bool]:
    """Classify a clause into one of the four importance tiers.

    Returns (tier, matched_explicitly). Precedence when multiple signals
    coexist in one clause: required > preferred > contextual > the
    running section default — an explicit gating marker always wins over
    a softer contextual-mention phrase.
    """
    lowered = clause.lower()

    if any(marker in lowered for marker in REQUIRED_MARKERS):
        return "required", True

    if any(marker in lowered for marker in PREFERRED_MARKERS):
        return "preferred", True

    if any(marker in lowered for marker in CONTEXTUAL_MARKERS):
        return "contextual", True

    return default, False


def is_hard_requirement(clause: str) -> bool:
    lowered = clause.lower()
    return any(marker in lowered for marker in HARD_REQUIREMENT_MARKERS)


def iter_clauses_with_default_tier(
    text: str,
) -> list[tuple[ClauseSpan, Tier]]:
    """Clause-split `text` once, tracking a running section-level default
    tier (required -> preferred -> informational, as the corresponding
    section heading is encountered), mirroring AJI-012's clause-first
    `iter_clauses_with_default_level` so an inline marker is never
    separated from the clause it modifies.
    """
    default: Tier = "required"
    results: list[tuple[ClauseSpan, Tier]] = []

    for clause_span in split_clauses_with_spans(text):
        heading = clause_span.text.strip().rstrip(":").strip().lower()

        if heading in PREFERRED_SECTION_MARKERS:
            default = "preferred"
            continue

        if heading in INFORMATIONAL_SECTION_MARKERS:
            default = "informational"
            continue

        results.append((clause_span, default))

    return results


# ---------------------------------------------------------------------------
# Prompt-injection detection (diagnostic only — see contracts.py's
# `SecurityDiagnostics` docstring for why this is never corrective).
# ---------------------------------------------------------------------------

_PROMPT_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(
            r"ignore (?:all )?(?:previous|prior|above) instructions",
            re.IGNORECASE,
        ),
    ),
    (
        "disregard_instructions",
        re.compile(
            r"disregard (?:all )?(?:previous|prior|the above)", re.IGNORECASE
        ),
    ),
    ("new_instructions", re.compile(r"\bnew instructions?\s*:", re.IGNORECASE)),
    ("role_override", re.compile(r"\byou are now\b", re.IGNORECASE)),
    (
        "system_prompt_claim",
        re.compile(r"\b(?:system prompt|system message)\b", re.IGNORECASE),
    ),
    (
        "override_rules",
        re.compile(r"override (?:your|the) (?:instructions|rules)", re.IGNORECASE),
    ),
    (
        "fake_role_tag",
        re.compile(r"^\s*(?:system|assistant)\s*:", re.IGNORECASE | re.MULTILINE),
    ),
    (
        "mark_as_qualified",
        re.compile(
            r"(?:mark|rate|score|classify) (?:this|the) "
            r"(?:candidate|resume|applicant) as",
            re.IGNORECASE,
        ),
    ),
)


def detect_prompt_injection_signals(text: str) -> list[PromptInjectionSignal]:
    """Detect JD text that attempts to redirect the downstream AI
    decoding stage's behavior. Purely diagnostic/audit — detected text is
    never stripped from what is sent to the AI stage (see module
    docstring); the real safety boundary is the evidence-substring
    anti-hallucination check in validator.py, which holds regardless of
    what an embedded instruction asks for.
    """
    if not text:
        return []

    signals: list[PromptInjectionSignal] = []

    for label, pattern in _PROMPT_INJECTION_PATTERNS:
        match = pattern.search(text)

        if match:
            signals.append(
                PromptInjectionSignal(
                    pattern_label=label, evidence_text=match.group(0)
                )
            )

    return signals


# ---------------------------------------------------------------------------
# Skills (as RequirementItems)
# ---------------------------------------------------------------------------

_EQUIVALENT_PATTERN = re.compile(
    r"\bor equivalent\b([^.;\n]*)", re.IGNORECASE
)
_NEGATED_REQUIREMENT_PATTERN = re.compile(
    r"\bno\b[^.;\n]*\brequired\b|\bnot required\b|\bnot\s+necessary\b",
    re.IGNORECASE,
)


def _equivalent_alternative_text(clause: str) -> str | None:
    match = _EQUIVALENT_PATTERN.search(clause)

    if not match:
        return None

    trailing = match.group(0).strip()
    return trailing if trailing else None


@dataclass
class ExtractionContext:
    """Accumulates items/groups/negated-mentions across every extraction
    pass so relationship-group and contradiction detection can run once,
    at the end, over the full JD rather than per-clause."""

    items: list[RequirementItem] = field(default_factory=list)
    groups: list[RequirementGroup] = field(default_factory=list)
    # ids of the (informational-tier) items created for a JD clause that
    # explicitly negates a skill ("no X experience required") — kept as
    # real items (not a bare string set) so they participate in the same
    # duplicate-signature grouping as a genuine requirement of the same
    # skill, letting `detect_contradictions` flag the conflict with a
    # valid >=2-member `Contradiction` rather than a synthetic single-id
    # one.
    negation_item_ids: set[str] = field(default_factory=set)
    id_allocator: IdAllocator = field(default_factory=lambda: IdAllocator("req"))
    group_allocator: IdAllocator = field(
        default_factory=lambda: IdAllocator("grp")
    )


def extract_skill_items(
    text: str,
    ctx: ExtractionContext,
    *,
    skip_starts: frozenset[int] = frozenset(),
) -> None:
    for clause_span, default_tier in iter_clauses_with_default_tier(text):
        if clause_span.start in skip_starts:
            # Already modeled as a MIN_COUNT set by
            # `extract_min_count_items` — skipping here prevents the same
            # skill mention from also being captured as an ordinary
            # required/preferred item, which would let `merge_duplicates`
            # silently discard its MIN_COUNT semantics in favor of
            # whichever occurrence has the higher importance rank.
            continue

        clause = clause_span.text

        if _NEGATED_REQUIREMENT_PATTERN.search(clause):
            for skill in find_protected_skills(clause):
                item_id = ctx.id_allocator.next()
                ctx.negation_item_ids.add(item_id)
                ctx.items.append(
                    RequirementItem(
                        id=item_id,
                        requirement_type="skill",
                        importance="informational",
                        hard_requirement=False,
                        statement=f"{skill} (explicitly not required)",
                        canonical_terms=[skill],
                        raw_text=clause,
                        source_span={
                            "text": clause,
                            "start": clause_span.start,
                            "end": clause_span.end,
                        },
                        confidence="medium",
                        ambiguous=True,
                        ambiguity_reason=(
                            "The JD explicitly states this is not required "
                            "here."
                        ),
                    )
                )
            continue

        skills = find_protected_skills(clause)

        if not skills:
            continue

        tier, matched = classify_tier(clause, default=default_tier)
        hard = tier == "required" and is_hard_requirement(clause)
        confidence = "high" if matched else "medium"

        has_and = bool(_CLAUSE_HAS_AND.search(clause))
        has_or = bool(_CLAUSE_HAS_OR.search(clause))
        mixed_connectors = has_and and has_or

        equivalent_text = _equivalent_alternative_text(clause)

        clause_item_ids: list[str] = []

        for skill in skills:
            item_id = ctx.id_allocator.next()
            clause_item_ids.append(item_id)

            ambiguous = mixed_connectors
            ambiguity_reason = (
                "Clause mixes 'and'/'or' connectors; the relationship "
                "between the requirements it lists could not be reliably "
                "determined."
                if mixed_connectors
                else None
            )

            ctx.items.append(
                RequirementItem(
                    id=item_id,
                    requirement_type="skill",
                    importance=tier,
                    hard_requirement=hard,
                    statement=f"{skill} ({tier})",
                    canonical_terms=[skill],
                    raw_text=clause,
                    source_span={
                        "text": clause,
                        "start": clause_span.start,
                        "end": clause_span.end,
                    },
                    confidence=confidence,
                    ambiguous=ambiguous,
                    ambiguity_reason=ambiguity_reason,
                    equivalent_alternatives=(
                        [equivalent_text] if equivalent_text else []
                    ),
                )
            )

        if mixed_connectors or len(clause_item_ids) < 2:
            if equivalent_text and len(clause_item_ids) == 1:
                ctx.groups.append(
                    RequirementGroup(
                        id=ctx.group_allocator.next(),
                        relationship="EQUIVALENT",
                        member_ids=clause_item_ids,
                        description=(
                            f"{skills[0]} is interchangeable with a "
                            "JD-stated equivalent alternative."
                        ),
                        evidence_text=clause,
                    )
                )
            continue

        if has_or:
            ctx.groups.append(
                RequirementGroup(
                    id=ctx.group_allocator.next(),
                    relationship="OR",
                    member_ids=clause_item_ids,
                    description=(
                        "Any one of these requirements satisfies this "
                        "clause."
                    ),
                    evidence_text=clause,
                )
            )
        elif has_and:
            ctx.groups.append(
                RequirementGroup(
                    id=ctx.group_allocator.next(),
                    relationship="AND",
                    member_ids=clause_item_ids,
                    description="All of these requirements are needed.",
                    evidence_text=clause,
                )
            )

        if equivalent_text:
            ctx.groups.append(
                RequirementGroup(
                    id=ctx.group_allocator.next(),
                    relationship="EQUIVALENT",
                    member_ids=[clause_item_ids[0]],
                    description=(
                        f"{skills[0]} is interchangeable with a "
                        "JD-stated equivalent alternative."
                    ),
                    evidence_text=clause,
                )
            )


_MIN_COUNT_PATTERN = re.compile(
    r"at least (\d+) of (?:the following|these)|"
    r"(\d+)\+?\s+of the following|"
    r"any (\d+) of",
    re.IGNORECASE,
)


def extract_min_count_items(
    text: str, ctx: ExtractionContext
) -> frozenset[int]:
    """"Proficiency in at least N of: A, B, C"-style clauses.

    The clause itself and (when the list is inline) the immediately
    following clause are scanned for canonical skills; a MIN_COUNT group
    is only created when at least `N` distinct canonical skills were
    actually found, and `minimum_count` is capped to the member count
    found — this module never fabricates a member it has no evidence
    for.

    Returns the set of clause start-offsets consumed this way, so the
    caller can exclude them from the ordinary required/preferred skill
    pass (see `extract_skill_items`'s `skip_starts`).
    """
    clauses = iter_clauses_with_default_tier(text)
    consumed_starts: set[int] = set()

    for index, (clause_span, _default_tier) in enumerate(clauses):
        clause = clause_span.text
        match = _MIN_COUNT_PATTERN.search(clause)

        if not match:
            continue

        n = int(next(group for group in match.groups() if group))

        skills = find_protected_skills(clause)

        # A "the following" style list is often on the next clause
        # (colon-separated list split into its own clause by
        # `split_clauses_with_spans`).
        if not skills and index + 1 < len(clauses):
            next_clause_span, _ = clauses[index + 1]
            skills = find_protected_skills(next_clause_span.text)
            evidence_span = next_clause_span
        else:
            evidence_span = clause_span

        if len(skills) < 2:
            continue

        consumed_starts.add(clause_span.start)
        consumed_starts.add(evidence_span.start)

        member_ids: list[str] = []

        for skill in skills:
            item_id = ctx.id_allocator.next()
            member_ids.append(item_id)

            ctx.items.append(
                RequirementItem(
                    id=item_id,
                    requirement_type="skill",
                    importance="preferred",
                    hard_requirement=False,
                    statement=f"{skill} (part of an at-least-{n}-of set)",
                    canonical_terms=[skill],
                    raw_text=evidence_span.text,
                    source_span={
                        "text": evidence_span.text,
                        "start": evidence_span.start,
                        "end": evidence_span.end,
                    },
                    confidence="medium",
                    ambiguous=True,
                    ambiguity_reason=(
                        f"Part of an 'at least {n} of the following' "
                        "requirement; individual necessity is not "
                        "guaranteed."
                    ),
                )
            )

        ctx.groups.append(
            RequirementGroup(
                id=ctx.group_allocator.next(),
                relationship="MIN_COUNT",
                member_ids=member_ids,
                minimum_count=min(n, len(member_ids)),
                description=f"At least {min(n, len(member_ids))} of these are required.",
                evidence_text=clause,
            )
        )

    return frozenset(consumed_starts)


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------

_YEARS_RANGE_PATTERN = re.compile(
    r"(?P<min>\d+(?:\.\d+)?)\s*(?:-|to)\s*(?P<max>\d+(?:\.\d+)?)\+?\s+years?\b",
    re.IGNORECASE,
)
_YEARS_AT_LEAST_PATTERN = re.compile(
    r"(?P<years>\d+(?:\.\d+)?)\+\s+years?\b", re.IGNORECASE
)
_YEARS_UP_TO_PATTERN = re.compile(
    r"up to (?P<years>\d+(?:\.\d+)?)\s+years?\b", re.IGNORECASE
)
_YEARS_PLAIN_PATTERN = re.compile(
    r"(?P<years>\d+(?:\.\d+)?)\s+years?\b", re.IGNORECASE
)

_EXPERIENCE_CONTEXT_KEYWORDS = (
    "production",
    "leadership",
    "management",
    "enterprise",
    "hands-on",
    "hands on",
)


def _parse_experience(clause: str) -> ExperienceConstraint | None:
    range_match = _YEARS_RANGE_PATTERN.search(clause)

    if range_match:
        minimum = float(range_match.group("min"))
        maximum = float(range_match.group("max"))
        operator: Literal["range"] = "range"
        return ExperienceConstraint(
            operator=operator, minimum_years=minimum, maximum_years=maximum
        )

    up_to_match = _YEARS_UP_TO_PATTERN.search(clause)

    if up_to_match:
        return ExperienceConstraint(
            operator="at_most", maximum_years=float(up_to_match.group("years"))
        )

    at_least_match = _YEARS_AT_LEAST_PATTERN.search(clause)

    if at_least_match:
        return ExperienceConstraint(
            operator="at_least",
            minimum_years=float(at_least_match.group("years")),
        )

    plain_match = _YEARS_PLAIN_PATTERN.search(clause)

    if plain_match:
        return ExperienceConstraint(
            operator="at_least",
            minimum_years=float(plain_match.group("years")),
        )

    return None


def extract_experience_items(text: str, ctx: ExtractionContext) -> None:
    for clause_span, default_tier in iter_clauses_with_default_tier(text):
        clause = clause_span.text
        constraint = _parse_experience(clause)

        if constraint is None:
            continue

        tier, matched = classify_tier(clause, default=default_tier)
        hard = tier == "required" and is_hard_requirement(clause)
        confidence = "high" if matched else "medium"

        area_skills = find_protected_skills(clause)
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

        constraint.area = area
        constraint.context = context

        item_id = ctx.id_allocator.next()

        ctx.items.append(
            RequirementItem(
                id=item_id,
                requirement_type="experience",
                importance=tier,
                hard_requirement=hard,
                statement=(
                    f"{constraint.operator} experience"
                    + (f" in {area}" if area else "")
                ),
                canonical_terms=[area] if area else [],
                raw_text=clause,
                source_span={
                    "text": clause,
                    "start": clause_span.start,
                    "end": clause_span.end,
                },
                confidence=confidence,
                experience=constraint,
            )
        )


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


def extract_education_items(text: str, ctx: ExtractionContext) -> None:
    for clause_span, default_tier in iter_clauses_with_default_tier(text):
        clause = clause_span.text
        degree = _match_degree(clause)

        if degree is None:
            continue

        degree_level, field_of_study = degree
        tier, matched = classify_tier(clause, default=default_tier)
        hard = tier == "required" and is_hard_requirement(clause)
        confidence = "high" if matched else "medium"
        equivalent_text = _equivalent_alternative_text(clause)

        item_id = ctx.id_allocator.next()

        ctx.items.append(
            RequirementItem(
                id=item_id,
                requirement_type="education",
                importance=tier,
                hard_requirement=hard,
                statement=(
                    f"{degree_level}"
                    + (f" in {field_of_study}" if field_of_study else "")
                ),
                canonical_terms=[degree_level],
                raw_text=clause,
                source_span={
                    "text": clause,
                    "start": clause_span.start,
                    "end": clause_span.end,
                },
                confidence=confidence,
                education=EducationConstraint(
                    degree_level=degree_level, field_of_study=field_of_study
                ),
                equivalent_alternatives=(
                    [equivalent_text] if equivalent_text else []
                ),
            )
        )

        if equivalent_text:
            ctx.groups.append(
                RequirementGroup(
                    id=ctx.group_allocator.next(),
                    relationship="EQUIVALENT",
                    member_ids=[item_id],
                    description=(
                        f"{degree_level} is interchangeable with a "
                        "JD-stated equivalent alternative."
                    ),
                    evidence_text=clause,
                )
            )


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


def extract_certification_items(text: str, ctx: ExtractionContext) -> None:
    for clause_span, default_tier in iter_clauses_with_default_tier(text):
        clause = clause_span.text
        lowered = clause.lower()

        if not any(keyword in lowered for keyword in _CERTIFICATION_KEYWORDS):
            continue

        tier, matched = classify_tier(clause, default=default_tier)
        hard = tier == "required" and is_hard_requirement(clause)
        confidence = "high" if matched else "medium"
        equivalent_text = _equivalent_alternative_text(clause)

        item_id = ctx.id_allocator.next()

        ctx.items.append(
            RequirementItem(
                id=item_id,
                requirement_type="certification",
                importance=tier,
                hard_requirement=hard,
                statement=clause,
                canonical_terms=[],
                raw_text=clause,
                source_span={
                    "text": clause,
                    "start": clause_span.start,
                    "end": clause_span.end,
                },
                confidence=confidence,
                certification=CertificationConstraint(name=clause),
                equivalent_alternatives=(
                    [equivalent_text] if equivalent_text else []
                ),
            )
        )

        if equivalent_text:
            ctx.groups.append(
                RequirementGroup(
                    id=ctx.group_allocator.next(),
                    relationship="EQUIVALENT",
                    member_ids=[item_id],
                    description=(
                        "This certification is interchangeable with a "
                        "JD-stated equivalent alternative."
                    ),
                    evidence_text=clause,
                )
            )


# ---------------------------------------------------------------------------
# Responsibilities (always informational — never a scored requirement)
# ---------------------------------------------------------------------------

_BULLET_PATTERN = re.compile(r"^(?:[-•▪◦*]|\d+[.)])\s+")


def extract_responsibility_items(
    raw: RawRequirementSource, ctx: ExtractionContext
) -> None:
    text = raw.responsibilities

    if not text:
        return

    base_offset = full_source_text(raw).rfind(text)

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()

        if not line:
            continue

        cleaned = _BULLET_PATTERN.sub("", line).strip()

        if not cleaned or len(cleaned.split()) < 3:
            continue

        local_offset = line.find(cleaned)
        start = (
            base_offset + text.find(line) + local_offset
            if base_offset != -1
            else 0
        )

        item_id = ctx.id_allocator.next()

        ctx.items.append(
            RequirementItem(
                id=item_id,
                requirement_type="responsibility",
                importance="informational",
                hard_requirement=False,
                statement=cleaned,
                canonical_terms=find_protected_skills(cleaned),
                raw_text=cleaned,
                source_span=(
                    {
                        "text": cleaned,
                        "start": start,
                        "end": start + len(cleaned),
                    }
                    if start >= 0
                    else None
                ),
                confidence="high",
            )
        )


# ---------------------------------------------------------------------------
# Screening constraints (separate from scored requirements)
# ---------------------------------------------------------------------------

_BACKGROUND_CHECK_PATTERN = re.compile(
    r"background check|background screening", re.IGNORECASE
)
_DRUG_SCREENING_PATTERN = re.compile(
    r"drug (?:test|screen|screening)", re.IGNORECASE
)
_MINIMUM_AGE_PATTERN = re.compile(
    r"must be (?:at least )?(?:18|21) years? (?:of age|old)|"
    r"minimum age of \d+",
    re.IGNORECASE,
)
_DRIVERS_LICENSE_PATTERN = re.compile(
    r"valid driver'?s? licen[sc]e", re.IGNORECASE
)
_SPONSORSHIP_REQUIRED_PATTERN = re.compile(
    r"sponsorship\s+(?:is\s+)?required", re.IGNORECASE
)
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


def extract_screening_constraints(
    text: str, ctx: ExtractionContext
) -> list[ScreeningConstraint]:
    constraints: list[ScreeningConstraint] = []
    signals = extract_work_authorization_signals(text)

    for clause_span, _default_tier in iter_clauses_with_default_tier(text):
        clause = clause_span.text
        span = {"text": clause, "start": clause_span.start, "end": clause_span.end}

        if _BACKGROUND_CHECK_PATTERN.search(clause):
            constraints.append(
                ScreeningConstraint(
                    id=ctx.id_allocator.next(),
                    constraint_type="background_check",
                    status="required",
                    statement="A background check is required.",
                    raw_text=clause,
                    source_span=span,
                )
            )

        if _DRUG_SCREENING_PATTERN.search(clause):
            constraints.append(
                ScreeningConstraint(
                    id=ctx.id_allocator.next(),
                    constraint_type="drug_screening",
                    status="required",
                    statement="Drug screening is required.",
                    raw_text=clause,
                    source_span=span,
                )
            )

        if _MINIMUM_AGE_PATTERN.search(clause):
            constraints.append(
                ScreeningConstraint(
                    id=ctx.id_allocator.next(),
                    constraint_type="minimum_age",
                    status="required",
                    statement="A minimum age is required.",
                    raw_text=clause,
                    source_span=span,
                )
            )

        if _DRIVERS_LICENSE_PATTERN.search(clause):
            constraints.append(
                ScreeningConstraint(
                    id=ctx.id_allocator.next(),
                    constraint_type="drivers_license",
                    status="required",
                    statement="A valid driver's license is required.",
                    raw_text=clause,
                    source_span=span,
                )
            )

        sponsorship_match = _SPONSORSHIP_REQUIRED_PATTERN.search(clause)

        if sponsorship_match:
            constraints.append(
                ScreeningConstraint(
                    id=ctx.id_allocator.next(),
                    constraint_type="sponsorship",
                    status="required",
                    statement="Visa sponsorship eligibility is required.",
                    raw_text=clause,
                    source_span=span,
                )
            )

        citizenship_match = next(
            (
                pattern.search(clause)
                for pattern in _CITIZENSHIP_PREFERRED_PATTERNS
                if pattern.search(clause)
            ),
            None,
        )

        if citizenship_match:
            constraints.append(
                ScreeningConstraint(
                    id=ctx.id_allocator.next(),
                    constraint_type="citizenship",
                    status="preferred",
                    statement="Citizenship is preferred, not required.",
                    raw_text=clause,
                    source_span=span,
                )
            )

        clearance_match = next(
            (
                pattern.search(clause)
                for pattern in _CLEARANCE_PREFERRED_PATTERNS
                if pattern.search(clause)
            ),
            None,
        )

        if clearance_match:
            constraints.append(
                ScreeningConstraint(
                    id=ctx.id_allocator.next(),
                    constraint_type="security_clearance",
                    status="preferred",
                    statement="Security clearance is preferred, not required.",
                    raw_text=clause,
                    source_span=span,
                )
            )

    if signals.authorization_required or signals.citizenship_required:
        constraints.append(
            ScreeningConstraint(
                id=ctx.id_allocator.next(),
                constraint_type="work_authorization",
                status="disqualifying",
                statement=(
                    "Candidates must already be authorized to work; this "
                    "gates eligibility rather than being a scored skill."
                ),
                raw_text=text,
                source_span=None,
                confidence="medium",
            )
        )

    if signals.clearance_required and not clearance_match_any(constraints):
        constraints.append(
            ScreeningConstraint(
                id=ctx.id_allocator.next(),
                constraint_type="security_clearance",
                status="required",
                statement="A security clearance is required.",
                raw_text=text,
                source_span=None,
                confidence="medium",
            )
        )

    return constraints


def clearance_match_any(constraints: list[ScreeningConstraint]) -> bool:
    return any(
        c.constraint_type == "security_clearance" for c in constraints
    )


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
        for keyword in sorted(_SENIORITY_KEYWORDS, key=len, reverse=True)
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
# Duplicate detection / merging
# ---------------------------------------------------------------------------

def _duplicate_signature(item: RequirementItem) -> tuple[str, ...]:
    if item.requirement_type == "skill":
        return ("skill", *sorted(item.canonical_terms))

    if item.requirement_type == "experience" and item.experience:
        return ("experience", item.experience.area or "")

    if item.requirement_type == "education" and item.education:
        return (
            "education",
            item.education.degree_level or "",
            item.education.field_of_study or "",
        )

    if item.requirement_type == "certification":
        return ("certification", _normalize_for_comparison(item.statement))

    return (
        item.requirement_type,
        _normalize_for_comparison(item.raw_text),
    )


def merge_duplicates(
    items: list[RequirementItem], groups: list[RequirementGroup]
) -> tuple[list[RequirementItem], list[RequirementGroup], list[DuplicateGroup]]:
    """Collapse items that describe the same requirement (mentioned in
    multiple clauses) down to the single highest-importance occurrence,
    while keeping a `DuplicateGroup` diagnostic recording every occurrence
    that was collapsed. Relationship groups that referenced a collapsed
    (non-surviving) item are rewritten to point at the surviving item.
    """
    buckets: dict[tuple[str, ...], list[RequirementItem]] = defaultdict(list)

    for item in items:
        buckets[_duplicate_signature(item)].append(item)

    merged: list[RequirementItem] = []
    duplicate_groups: list[DuplicateGroup] = []
    substitutions: dict[str, str] = {}

    for signature, bucket in buckets.items():
        if len(bucket) == 1:
            merged.append(bucket[0])
            continue

        winner = max(
            bucket,
            key=lambda i: (
                _IMPORTANCE_RANK[i.importance],
                i.hard_requirement,
                i.confidence == "high",
            ),
        )
        merged.append(winner)

        for loser in bucket:
            if loser.id != winner.id:
                substitutions[loser.id] = winner.id

        duplicate_groups.append(
            DuplicateGroup(
                canonical_key="|".join(signature),
                member_ids=[i.id for i in bucket],
                note=(
                    f"Same {bucket[0].requirement_type} requirement "
                    f"mentioned {len(bucket)} times in the JD; kept the "
                    f"highest-importance occurrence ({winner.id})."
                ),
            )
        )

    rewritten_groups: list[RequirementGroup] = []

    for group in groups:
        new_member_ids: list[str] = []
        seen: set[str] = set()

        for member_id in group.member_ids:
            resolved = substitutions.get(member_id, member_id)

            if resolved not in seen:
                seen.add(resolved)
                new_member_ids.append(resolved)

        min_members = 1 if group.relationship == "EQUIVALENT" else 2

        if len(new_member_ids) < min_members:
            continue

        minimum_count = group.minimum_count

        if minimum_count is not None:
            minimum_count = min(minimum_count, len(new_member_ids))

        rewritten_groups.append(
            RequirementGroup(
                id=group.id,
                relationship=group.relationship,
                member_ids=new_member_ids,
                minimum_count=minimum_count,
                description=group.description,
                evidence_text=group.evidence_text,
            )
        )

    return merged, rewritten_groups, duplicate_groups


# ---------------------------------------------------------------------------
# Contradiction diagnostics
# ---------------------------------------------------------------------------

def detect_contradictions(
    duplicate_groups: list[DuplicateGroup],
    all_items_by_id: dict[str, RequirementItem],
    negation_item_ids: set[str],
) -> list[Contradiction]:
    """Detect JD-internal contradictions.

    Deliberately conservative and pattern-based (not exhaustive NLU-level
    contradiction reasoning): it only flags the cases below, each
    verifiable purely from already-extracted structured data.

    Every case here is derived from `duplicate_groups` — the same-
    signature groupings `merge_duplicates` already computed — rather than
    re-deriving grouping logic, and rather than scanning the (already
    collapsed) merged item list, which would hide a contradiction whose
    conflicting occurrences were merged away.
    """
    contradictions: list[Contradiction] = []

    for dup in duplicate_groups:
        member_items = [
            all_items_by_id[member_id]
            for member_id in dup.member_ids
            if member_id in all_items_by_id
        ]
        tiers = {item.importance for item in member_items}

        if len(tiers) > 1:
            has_negation = bool(set(dup.member_ids) & negation_item_ids)
            has_positive = any(
                item.importance in ("required", "preferred")
                for item in member_items
            )
            subject = dup.canonical_key.split("|", 1)[-1] or "this requirement"

            if has_negation and has_positive:
                contradictions.append(
                    Contradiction(
                        contradiction_type="conflicting_requirement_and_exclusion",
                        member_ids=dup.member_ids,
                        description=(
                            f"'{subject}' is both required/preferred and "
                            "explicitly stated as not required elsewhere "
                            "in the JD."
                        ),
                    )
                )
            else:
                contradictions.append(
                    Contradiction(
                        contradiction_type="conflicting_importance",
                        member_ids=dup.member_ids,
                        description=(
                            f"{subject} is described with conflicting "
                            f"importance ({', '.join(sorted(tiers))}) in "
                            "different parts of the JD."
                        ),
                    )
                )

        if not dup.canonical_key.startswith("experience|"):
            continue

        minimums = [
            item.experience.minimum_years
            for item in member_items
            if item.experience and item.experience.minimum_years is not None
        ]

        if len(minimums) < 2:
            continue

        if max(minimums) - min(minimums) >= 1:
            area = dup.canonical_key.split("|", 1)[-1] or "this area"
            contradictions.append(
                Contradiction(
                    contradiction_type="conflicting_experience_range",
                    member_ids=dup.member_ids,
                    description=(
                        f"Experience requirement for '{area}' varies across "
                        f"the JD ({sorted(set(minimums))} years)."
                    ),
                )
            )

    return contradictions


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@dataclass
class DeterministicExtraction:
    seniority: str | None
    requirements: list[RequirementItem]
    relationships: list[RequirementGroup]
    screening_constraints: list[ScreeningConstraint]
    duplicate_groups: list[DuplicateGroup]
    contradictions: list[Contradiction]
    ambiguous_requirement_ids: list[str]
    security_signals: list[PromptInjectionSignal]


def extract_deterministic(raw: RawRequirementSource) -> DeterministicExtraction:
    text = requirement_text(raw)
    ctx = ExtractionContext()

    # MIN_COUNT extraction runs first so its clauses can be excluded from
    # the ordinary skill pass below — otherwise the same skill mention
    # would be captured twice (once as a MIN_COUNT-set member, once as a
    # plain required/preferred item) and `merge_duplicates` would
    # silently discard the MIN_COUNT semantics in favor of whichever
    # occurrence ranks higher.
    min_count_clause_starts = extract_min_count_items(text, ctx)
    extract_skill_items(text, ctx, skip_starts=min_count_clause_starts)
    extract_experience_items(text, ctx)
    extract_education_items(text, ctx)
    extract_certification_items(text, ctx)
    extract_responsibility_items(raw, ctx)

    screening_constraints = extract_screening_constraints(text, ctx)

    merged_items, rewritten_groups, duplicate_groups = merge_duplicates(
        ctx.items, ctx.groups
    )

    all_items_by_id = {item.id: item for item in ctx.items}

    contradictions = detect_contradictions(
        duplicate_groups, all_items_by_id, ctx.negation_item_ids
    )

    ambiguous_ids = [item.id for item in merged_items if item.ambiguous]

    full_text = full_source_text(raw)
    security_signals = detect_prompt_injection_signals(full_text)

    return DeterministicExtraction(
        seniority=extract_seniority_from_title(raw.title),
        requirements=merged_items,
        relationships=rewritten_groups,
        screening_constraints=screening_constraints,
        duplicate_groups=duplicate_groups,
        contradictions=contradictions,
        ambiguous_requirement_ids=ambiguous_ids,
        security_signals=security_signals,
    )
