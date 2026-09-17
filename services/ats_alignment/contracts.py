"""ATS Alignment (AJI-013) pure, DB-free contracts.

This module has no dependency on apps.api (no DB, no FastAPI, no AI
provider) — mirroring services.job_matching's and services.eligibility's
own DB/AI-free-core convention. The apps.api orchestration layer
(apps/api/services/ats_alignment_service.py) is responsible for turning
ORM rows (Job, JobIntelligence, ResumeVersion, Profile) into the plain
dataclasses defined here before calling services.ats_alignment.engine.

Category taxonomy note: the AJI-013 spec describes three tiers
(Must-Have / Preferred / Nice-to-Have). The already-shipped AJI-012
`JobIntelligence` contract (apps/api/services/job_intelligence/contracts.py)
only distinguishes two levels — `required` and `preferred` — and
deliberately folds "nice to have"/"bonus"/"a plus" phrasing into
`preferred` (see its PREFERRED_MARKERS). Per the AJI-013 post-push
resolution, ATS Alignment reuses that same two-tier taxonomy exactly
(`must_have` == AJI-012 `required`, `preferred` == AJI-012 `preferred`)
rather than forking a third tier on top of AJI-012's classification
logic. `RequirementCategory` therefore has only two values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AlignmentStatus = Literal["matched", "partial", "missing"]
RequirementCategory = Literal["must_have", "preferred"]
RequirementType = Literal["skill", "experience", "education", "certification"]
Confidence = Literal["high", "medium", "low"]


@dataclass
class JobRequirementItem:
    """One atomic, independently-evaluable requirement extracted from a
    Job Intelligence (AJI-012) snapshot.

    `requirement_id` is a stable key (used as the JSON key/anchor in the
    persisted result) — it is not a database id.
    """

    requirement_id: str
    requirement_type: RequirementType
    category: RequirementCategory
    requirement_text: str
    jd_evidence: str

    canonical_skill: str | None = None
    minimum_years: float | None = None
    area: str | None = None
    degree_level: str | None = None
    field_of_study: str | None = None
    certification_name: str | None = None


@dataclass
class RequirementAlignment:
    """The ATS Alignment result for exactly one JobRequirementItem."""

    requirement_id: str
    requirement_type: RequirementType
    category: RequirementCategory
    requirement_text: str
    status: AlignmentStatus
    jd_evidence: str
    resume_evidence: str | None
    explanation: str
    confidence: Confidence


@dataclass
class AtsAlignmentResult:
    """The full ATS Alignment result for one (resume version, JD) pair."""

    overall_score: float
    confidence: Confidence
    requirement_results: list[RequirementAlignment] = field(default_factory=list)

    must_have_total: int = 0
    must_have_matched: int = 0
    preferred_total: int = 0
    preferred_matched: int = 0

    engine_version: str = "1.0.0"
    scoring_version: str = "placeholder-1.0"
