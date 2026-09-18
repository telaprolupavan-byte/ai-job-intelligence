"""The Requirement Intelligence contract (AJI-020A).

This is the canonical structured representation of "what does this JD
actually require, and how sure are we?" — a finer-grained requirement
*model* than AJI-012 `JobIntelligenceResult`. It intentionally sits
alongside (not on top of, and not merged with) `job_intelligence`: AJI-012
already answers "what does this specific job require?" for AJI-013 (ATS
Alignment), AJI-014 (Job Match Reconciliation), and AJI-015 (Gap
Analysis), and this ticket does not change any of that. Requirement
Intelligence exists to model the parts of a JD's requirement language
AJI-012's two-tier (required/preferred) `SkillRequirement`/
`ExperienceRequirement`/etc. shape deliberately does not attempt: a
four-tier importance taxonomy, explicit hard-requirement/gating
semantics, AND/OR/minimum-count/equivalency relationships between
requirements, character-offset provenance, per-item ambiguity, and
JD-level quality/security diagnostics (duplicates, contradictions, and
prompt-injection signals).

Per AJI-020A's scope: this module produces a structured, versioned
object. It does not score, arbitrate evidence, match against a resume,
compute gaps, or generate suggestions — those are explicitly out of
scope (see docs/ARCHITECTURE.md and the AJI-020A ticket).

Every model in this file is a closed schema (`extra="forbid"`) so
malformed deterministic/AI output is a validation error, never a
silently-accepted extra field — this is the concrete "deterministic
schema validation" AJI-020A asks for.

Fields are deliberately optional/`None` by default: absence of
observable evidence must remain absence, never a guessed value (the
same UNKNOWN/absence convention `job_intelligence` already established).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Confidence = Literal["high", "medium", "low"]

# Responsibilities are modeled as a requirement type so they share the
# same provenance/confidence/diagnostics machinery as every other
# requirement — but a `RequirementItem._check_consistency` validator
# below permanently forbids a responsibility from ever being classified
# "required"/"preferred", so it can never be silently promoted into a
# scored requirement (mirrors AJI-012's "responsibilities vs.
# requirements" rule, generalized to the four-tier taxonomy).
RequirementType = Literal[
    "skill",
    "experience",
    "education",
    "certification",
    "responsibility",
]

# required     - the JD states this is needed to be considered.
# preferred    - the JD states this is wanted but not mandatory.
# contextual   - the JD mentions this to describe the job/team/stack, not
#                as something the candidate must demonstrate (e.g. "our
#                backend is built with Go and Kubernetes").
# informational - purely descriptive JD content, never a requirement of
#                the candidate (e.g. a responsibility line, a benefits
#                mention that happens to name a tool).
ImportanceTier = Literal["required", "preferred", "contextual", "informational"]

RelationshipType = Literal["AND", "OR", "MIN_COUNT", "EQUIVALENT"]

ScreeningConstraintType = Literal[
    "work_authorization",
    "sponsorship",
    "citizenship",
    "security_clearance",
    "background_check",
    "drug_screening",
    "minimum_age",
    "drivers_license",
    "other",
]

ScreeningConstraintStatus = Literal[
    "required", "preferred", "disqualifying", "unknown"
]

ExperienceOperator = Literal["at_least", "at_most", "exact", "range"]

ExtractionStatus = Literal["complete", "partial"]

ContradictionType = Literal[
    "conflicting_importance",
    "conflicting_experience_range",
    "conflicting_requirement_and_exclusion",
]


class SourceSpan(BaseModel):
    """A verbatim provenance pointer into the exact raw JD text this
    pipeline was given (never into a normalized/lowercased copy), so a
    consumer can highlight the exact source substring an item was
    extracted from. `start`/`end` are validated to actually bound `text`
    (see `_check_span`) rather than being trusted as opaque integers.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_span(self) -> "SourceSpan":
        if self.end <= self.start:
            raise ValueError("source span end must be after start")

        if self.end - self.start != len(self.text):
            raise ValueError("source span length must match text length")

        return self


class ExperienceConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator: ExperienceOperator
    minimum_years: float | None = None
    maximum_years: float | None = None
    area: str | None = None
    context: str | None = None


class EducationConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degree_level: str | None = None
    field_of_study: str | None = None


class CertificationConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class RequirementItem(BaseModel):
    """One extracted requirement, responsibility, or contextual mention.

    Type-specific detail lives in one of `experience`/`education`/
    `certification` (only the field matching `requirement_type` is ever
    populated) rather than a tagged union, so this stays a single closed
    schema OpenAI Structured Outputs (strict mode) can express, matching
    the rest of this codebase's AI-contract convention.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    requirement_type: RequirementType
    importance: ImportanceTier
    hard_requirement: bool = False

    statement: str = Field(min_length=1)
    canonical_terms: list[str] = Field(default_factory=list)

    raw_text: str = Field(min_length=1)
    source_span: SourceSpan | None = None
    confidence: Confidence = "high"

    ambiguous: bool = False
    ambiguity_reason: str | None = None

    experience: ExperienceConstraint | None = None
    education: EducationConstraint | None = None
    certification: CertificationConstraint | None = None

    # Free-text "or equivalent ..." alternatives the JD itself offered,
    # kept verbatim rather than resolved to a fabricated second canonical
    # requirement (see docs on `RequirementGroup` EQUIVALENT groups and
    # "do not fabricate taxonomy equivalences" in the AJI-020A ticket).
    equivalent_alternatives: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_consistency(self) -> "RequirementItem":
        if self.hard_requirement and self.importance != "required":
            raise ValueError(
                "hard_requirement items must have importance='required'"
            )

        if self.requirement_type == "responsibility" and self.importance in (
            "required",
            "preferred",
        ):
            raise ValueError(
                "responsibilities must never be classified as a "
                "required/preferred requirement"
            )

        return self


class RequirementGroup(BaseModel):
    """A logical relationship between two or more `RequirementItem`s.

    - AND: every member must be satisfied.
    - OR: any one member satisfies the group.
    - MIN_COUNT: at least `minimum_count` of the members must be
      satisfied (e.g. "proficiency in at least 2 of: React, Vue,
      Angular").
    - EQUIVALENT: the single member is explicitly interchangeable with a
      JD-stated alternative that could not be resolved to a second
      canonical requirement (see `RequirementItem.equivalent_alternatives`
      for the alternative's verbatim text) — never fabricated as a second
      structured requirement.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    relationship: RelationshipType
    member_ids: list[str] = Field(default_factory=list)
    minimum_count: int | None = None
    description: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_group(self) -> "RequirementGroup":
        if self.relationship == "MIN_COUNT":
            if self.minimum_count is None or self.minimum_count < 1:
                raise ValueError(
                    "MIN_COUNT group requires a positive minimum_count"
                )

            if self.minimum_count > len(self.member_ids):
                raise ValueError(
                    "minimum_count cannot exceed the number of members"
                )
        elif self.minimum_count is not None:
            raise ValueError("minimum_count only applies to MIN_COUNT groups")

        min_members = 1 if self.relationship == "EQUIVALENT" else 2

        if len(self.member_ids) < min_members:
            raise ValueError(
                f"{self.relationship} group requires at least "
                f"{min_members} member(s)"
            )

        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("a group's member_ids must not repeat")

        return self


class ScreeningConstraint(BaseModel):
    """A pass/fail gating condition unrelated to skill assessment (work
    authorization, clearance, background/drug screening, age, license,
    ...). Deliberately never mixed into `requirements` — a screening
    constraint is not something evidence is arbitrated/scored against,
    it is a binary gate (mirrors AJI-012's `AuthorizationSignals` being
    separate from skills/experience, generalized to the wider set of
    screening gates a JD can state).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    constraint_type: ScreeningConstraintType
    status: ScreeningConstraintStatus = "unknown"
    statement: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    source_span: SourceSpan | None = None
    confidence: Confidence = "high"


class TitleSeniorityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_title: str = Field(min_length=1)
    normalized_title: str | None = None
    normalized_title_confidence: Confidence | None = None
    normalized_title_evidence: str | None = None
    seniority: str | None = None
    seniority_confidence: Confidence | None = None
    seniority_evidence: str | None = None
    role_family: str | None = None
    role_family_confidence: Confidence | None = None
    role_family_evidence: str | None = None


class DomainTerminology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    confidence: Confidence | None = None
    evidence_text: str | None = None
    related_terms: list[str] = Field(default_factory=list)


class DuplicateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_key: str = Field(min_length=1)
    member_ids: list[str] = Field(min_length=2)
    note: str = Field(min_length=1)


class Contradiction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contradiction_type: ContradictionType
    member_ids: list[str] = Field(min_length=2)
    description: str = Field(min_length=1)


class QualityDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    ambiguous_requirement_ids: list[str] = Field(default_factory=list)


class PromptInjectionSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_label: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class SecurityDiagnostics(BaseModel):
    """JD-text prompt-injection visibility (AJI-020A).

    This is deliberately *diagnostic*, not corrective: the JD text is
    never mutated/redacted before being sent to the AI stage (surgically
    "cleaning" attacker-controlled text is its own injection surface, and
    would risk destroying legitimate JD content that happens to match a
    pattern). The actual safety boundary is structural — see
    `validator.py`'s evidence-substring check, which drops any AI-claimed
    field whose evidence does not verbatim-match the source text,
    regardless of what an embedded instruction asked the model to do.
    `signals` exists so a caller can flag/audit a JD that attempted it.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_injection_detected: bool = False
    signals: list[PromptInjectionSignal] = Field(default_factory=list)


class RequirementIntelligenceResult(BaseModel):
    """The full, versioned Requirement Intelligence contract for one JD
    snapshot."""

    model_config = ConfigDict(extra="forbid")

    analysis_version: str = Field(min_length=1)
    analyzer_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    model_provider: str | None = None
    model_name: str | None = None
    extraction_status: ExtractionStatus = "complete"

    # Opaque identifier of the JD source supplied by the caller (e.g. a
    # job id, or a content hash). This module has no dependency on the
    # `Job` ORM model or a database session — see service.py.
    source_id: str = Field(min_length=1)

    identity: TitleSeniorityInfo
    domain: DomainTerminology = Field(default_factory=DomainTerminology)

    requirements: list[RequirementItem] = Field(default_factory=list)
    relationships: list[RequirementGroup] = Field(default_factory=list)
    screening_constraints: list[ScreeningConstraint] = Field(
        default_factory=list
    )

    quality: QualityDiagnostics = Field(default_factory=QualityDiagnostics)
    security: SecurityDiagnostics = Field(default_factory=SecurityDiagnostics)

    @model_validator(mode="after")
    def _check_referential_integrity(self) -> "RequirementIntelligenceResult":
        requirement_ids = [item.id for item in self.requirements]

        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError("requirement ids must be unique")

        known_ids = set(requirement_ids)

        group_ids = [group.id for group in self.relationships]

        if len(set(group_ids)) != len(group_ids):
            raise ValueError("relationship group ids must be unique")

        for group in self.relationships:
            for member_id in group.member_ids:
                if member_id not in known_ids:
                    raise ValueError(
                        f"relationship group {group.id!r} references "
                        f"unknown requirement id {member_id!r}"
                    )

        constraint_ids = [item.id for item in self.screening_constraints]

        if len(set(constraint_ids)) != len(constraint_ids):
            raise ValueError("screening constraint ids must be unique")

        for requirement_id in self.quality.ambiguous_requirement_ids:
            if requirement_id not in known_ids:
                raise ValueError(
                    "quality.ambiguous_requirement_ids references unknown "
                    f"requirement id {requirement_id!r}"
                )

        return self
