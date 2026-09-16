from dataclasses import dataclass, field
from enum import Enum


class MatchStatus(str, Enum):
    MATCHED = "matched"
    MISSING = "missing"
    UNCERTAIN = "uncertain"


class EvidenceType(str, Enum):
    EXPLICIT = "explicit"
    EXPERIENCE = "experience"
    PROJECT = "project"
    EDUCATION = "education"
    INFERRED = "inferred"
    NONE = "none"


@dataclass
class SkillEvidence:
    skill: str
    status: MatchStatus
    evidence_type: EvidenceType
    evidence: str | None = None


@dataclass
class MatchComponent:
    name: str
    score: float
    max_score: float
    explanation: str


@dataclass
class JobMatchResult:
    score: float
    confidence: str

    must_have_matches: list[SkillEvidence] = field(default_factory=list)
    must_have_gaps: list[SkillEvidence] = field(default_factory=list)

    preferred_matches: list[SkillEvidence] = field(default_factory=list)
    preferred_gaps: list[SkillEvidence] = field(default_factory=list)

    components: list[MatchComponent] = field(default_factory=list)

    strengths: list[str] = field(default_factory=list)
    skill_gaps: list[str] = field(default_factory=list)

    engine_version: str = "1.0.0"


@dataclass
class ExperienceRequirement:
    minimum_years: float | None = None
    maximum_years: float | None = None
    description: str | None = None


@dataclass
class JobRequirements:
    must_have_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)

    must_have_experience: list[ExperienceRequirement] = field(
        default_factory=list
    )
    preferred_experience: list[ExperienceRequirement] = field(
        default_factory=list
    )


@dataclass
class ResumeEvidence:
    skills: list[str] = field(default_factory=list)
    experience_years: float | None = None
    evidence: list[SkillEvidence] = field(default_factory=list)