"""Thin adapters that run NERO's existing production pipelines on
evaluation cases, with no database.

Nothing here reimplements extraction, matching or validation. Each
function assembles the same inputs the production service assembles
from a `Job`/`ResumeVersion` row and then calls the production modules
directly:

- Job Intelligence: `job_intelligence.deterministic.extract_deterministic`
  + `job_intelligence.validator.build_job_intelligence_result`, exactly as
  `job_intelligence.service.generate_job_intelligence` does. That service
  needs a `Job` row, so its body is mirrored here (inputs, the AI
  `deterministic_context`, and the raw-text layout used for grounding).
- Requirement Intelligence: its deterministic extractor + validator, as
  `requirement_intelligence.service.build_requirement_intelligence` does.
- Job Match: `job_match_service._build_job_requirements` (the production
  Job Intelligence -> JobRequirements mapping) + `JobMatchingService`.
- Gap Analysis candidates: `ats_alignment_service`'s production
  Requirement Intelligence mapping + `evaluate_ats_alignment` +
  `gap_analysis.engine.select_gap_candidates`.

Deterministic mode passes `ai_semantics=None`. That is the same code path
production takes when the AI stage is unavailable (a "partial" snapshot),
and none of the AI-decoded fields (title/role family/domain, or seniority
when the title has none) feed skills, experience, matching or gaps.
Live mode calls the existing provider factories; see `live_*` below.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from apps.api.services.ats_alignment_service import (
    _build_job_requirements_from_requirement_intelligence,
)
from apps.api.services.gap_analysis.engine import GapCandidate, select_gap_candidates
from apps.api.services.job_intelligence.contracts import JobIntelligenceResult
from apps.api.services.job_intelligence.deterministic import (
    RawJobDescription,
    extract_deterministic as extract_job_deterministic,
)
from apps.api.services.job_intelligence.interpreter import (
    JobIntelligenceInterpreter,
)
from apps.api.services.job_intelligence.service import (
    ANALYSIS_VERSION as JOB_ANALYSIS_VERSION,
)
from apps.api.services.job_intelligence.validator import (
    build_job_intelligence_result,
)
from apps.api.services.job_match_service import _build_job_requirements
from apps.api.services.requirement_intelligence.contracts import (
    RequirementIntelligenceResult,
)
from apps.api.services.requirement_intelligence.deterministic import (
    RawRequirementSource,
    extract_deterministic as extract_requirement_deterministic,
)
from apps.api.services.requirement_intelligence.interpreter import (
    PROMPT_VERSION as REQUIREMENT_PROMPT_VERSION,
    RequirementIntelligenceInterpreter,
)
from apps.api.services.requirement_intelligence.service import (
    ANALYSIS_VERSION as REQUIREMENT_ANALYSIS_VERSION,
    ANALYZER_VERSION as REQUIREMENT_ANALYZER_VERSION,
    _raw_text as requirement_raw_text,
)
from apps.api.services.requirement_intelligence.validator import (
    build_requirement_intelligence_result,
)
from apps.api.services.resume_ai.deterministic import (
    DeterministicResumeAnalysis,
    analyze_resume_deterministically,
)
from services.ai_evaluation.dataset import JobCase, MatchCase, ResumeCase
from services.ats_alignment.engine import evaluate_ats_alignment
from services.ats_alignment.resume_adapter import build_resume_evidence_profile
from services.job_matching.contracts import JobMatchResult
from services.job_matching.resume_adapter import build_resume_evidence_from_analysis
from services.job_matching.service import JobMatchingService


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------


def analyze_resume(resume: ResumeCase) -> DeterministicResumeAnalysis:
    return analyze_resume_deterministically(resume.text.strip())


# ---------------------------------------------------------------------------
# Job Intelligence
# ---------------------------------------------------------------------------


def raw_job_description(job: JobCase) -> RawJobDescription:
    fields = job.job
    return RawJobDescription(
        title=fields.title,
        description=fields.text("description"),
        requirements=fields.text("requirements"),
        responsibilities=fields.text("responsibilities"),
        location=fields.location,
        country=fields.country or None,
        remote_type=fields.remote_type,
        employment_type=fields.employment_type,
        salary_min=fields.salary_min,
        salary_max=fields.salary_max,
        salary_currency=fields.salary_currency,
    )


def job_raw_text(job: JobCase) -> str:
    """The text Job Intelligence grounds AI evidence against
    (mirrors `job_intelligence.service._raw_jd_text`)."""
    fields = job.job
    return "\n".join(
        part
        for part in [
            fields.title,
            fields.location,
            fields.text("description"),
            fields.text("requirements"),
            fields.text("responsibilities"),
        ]
        if part
    )


def _job_deterministic_context(deterministic) -> dict[str, Any]:
    # Mirrors job_intelligence.service.generate_job_intelligence.
    return {
        "employment_type": deterministic.employment.employment_type,
        "seniority": deterministic.seniority,
        "required_skills": [
            item.canonical_skill for item in deterministic.required_skills
        ],
        "preferred_skills": [
            item.canonical_skill for item in deterministic.preferred_skills
        ],
    }


def run_job_intelligence(
    job: JobCase,
    *,
    ai_semantics: dict[str, Any] | None = None,
) -> JobIntelligenceResult:
    deterministic = extract_job_deterministic(raw_job_description(job))

    return build_job_intelligence_result(
        job_id=job.id,
        analysis_version=JOB_ANALYSIS_VERSION,
        raw_title=job.job.title,
        raw_text=job_raw_text(job),
        deterministic=deterministic,
        ai_semantics=ai_semantics,
    )


def live_job_intelligence(job: JobCase, provider) -> tuple[dict, JobIntelligenceResult]:
    """Run the AI semantic stage through the existing interpreter and
    validator. Returns (raw AI proposal, validated result) so the
    evaluation can see what the validator accepted and what it dropped."""
    deterministic = extract_job_deterministic(raw_job_description(job))
    interpretation = JobIntelligenceInterpreter(provider).analyze(
        raw_jd_text=job_raw_text(job),
        deterministic_context=_job_deterministic_context(deterministic),
    )
    result = build_job_intelligence_result(
        job_id=job.id,
        analysis_version=JOB_ANALYSIS_VERSION,
        raw_title=job.job.title,
        raw_text=job_raw_text(job),
        deterministic=deterministic,
        ai_semantics=interpretation.result,
    )
    return interpretation.result, result


# ---------------------------------------------------------------------------
# Requirement Intelligence
# ---------------------------------------------------------------------------


def raw_requirement_source(job: JobCase) -> RawRequirementSource:
    fields = job.job
    return RawRequirementSource(
        title=fields.title,
        description=fields.text("description"),
        requirements=fields.text("requirements"),
        responsibilities=fields.text("responsibilities"),
    )


def _requirement_deterministic_context(deterministic) -> dict[str, Any]:
    # Mirrors requirement_intelligence.service.build_requirement_intelligence.
    return {
        "seniority": deterministic.seniority,
        "required_skills": [
            item.canonical_terms[0]
            for item in deterministic.requirements
            if item.requirement_type == "skill"
            and item.importance == "required"
            and item.canonical_terms
        ],
        "preferred_skills": [
            item.canonical_terms[0]
            for item in deterministic.requirements
            if item.requirement_type == "skill"
            and item.importance == "preferred"
            and item.canonical_terms
        ],
    }


def _build_requirement_result(
    job: JobCase,
    deterministic,
    *,
    ai_semantics: dict[str, Any] | None,
    provider=None,
) -> RequirementIntelligenceResult:
    raw = raw_requirement_source(job)
    return build_requirement_intelligence_result(
        source_id=job.id,
        analysis_version=REQUIREMENT_ANALYSIS_VERSION,
        analyzer_version=REQUIREMENT_ANALYZER_VERSION,
        prompt_version=REQUIREMENT_PROMPT_VERSION,
        model_provider=getattr(provider, "provider_name", None),
        model_name=getattr(provider, "model_name", None),
        extraction_status="complete" if ai_semantics is not None else "partial",
        raw_title=raw.title,
        raw_text=requirement_raw_text(raw),
        deterministic=deterministic,
        ai_semantics=ai_semantics,
    )


def run_requirement_intelligence(job: JobCase) -> RequirementIntelligenceResult:
    deterministic = extract_requirement_deterministic(raw_requirement_source(job))
    return _build_requirement_result(job, deterministic, ai_semantics=None)


def live_requirement_intelligence(
    job: JobCase, provider
) -> tuple[dict, RequirementIntelligenceResult]:
    raw = raw_requirement_source(job)
    deterministic = extract_requirement_deterministic(raw)
    interpretation = RequirementIntelligenceInterpreter(provider).analyze(
        raw_jd_text=requirement_raw_text(raw),
        deterministic_context=_requirement_deterministic_context(deterministic),
    )
    result = _build_requirement_result(
        job, deterministic, ai_semantics=interpretation.result, provider=provider
    )
    return interpretation.result, result


def requirement_source_text(job: JobCase) -> str:
    """The exact text Requirement Intelligence source spans index into
    (mirrors `requirement_intelligence.deterministic.full_source_text`)."""
    fields = job.job
    return "\n".join(
        part
        for part in [
            fields.text("description"),
            fields.text("requirements"),
            fields.text("responsibilities"),
        ]
        if part
    )


# ---------------------------------------------------------------------------
# Job Match
# ---------------------------------------------------------------------------


def run_job_match(
    resume: ResumeCase, job: JobCase, case: MatchCase
) -> JobMatchResult:
    """Mirror `job_match_service.calculate_job_match` for a user with no
    target titles and no job preferences; `profile_years_experience`
    stands in for the user's profile field."""
    intelligence = run_job_intelligence(job)
    resume_evidence = build_resume_evidence_from_analysis(
        analyze_resume(resume),
        experience_years=case.profile_years_experience,
    )

    return JobMatchingService().calculate_match(
        job_title=job.job.title,
        job_requirements=_build_job_requirements(intelligence),
        resume_evidence=resume_evidence,
        resume_titles=[],
        job_remote_type=job.job.remote_type,
        job_location=job.job.location,
        job_employment_type=job.job.employment_type,
    )


# ---------------------------------------------------------------------------
# Gap Analysis (deterministic gap selection)
# ---------------------------------------------------------------------------


def run_gap_candidates(
    resume: ResumeCase, job: JobCase, case: MatchCase
) -> list[GapCandidate]:
    """Mirror `ats_alignment_service.calculate_ats_alignment` followed by
    `gap_analysis.service`'s candidate selection. The optional AI
    explanation stage never changes which requirements are gaps."""
    intelligence = run_requirement_intelligence(job)
    items, relationships, screening = (
        _build_job_requirements_from_requirement_intelligence(intelligence)
    )
    resume_text = resume.text.strip()
    profile = build_resume_evidence_profile(
        analyze_resume_deterministically(resume_text),
        raw_text=resume_text,
        years_experience=case.profile_years_experience,
    )
    result = evaluate_ats_alignment(
        items,
        profile,
        relationships=relationships,
        screening_constraints=screening,
    )

    if result is None:
        return []

    return select_gap_candidates(
        [asdict(item) for item in result.requirement_results]
    )


# ---------------------------------------------------------------------------
# Live LLM Resume Intelligence
# ---------------------------------------------------------------------------


def live_resume_intelligence(resume: ResumeCase, provider) -> dict:
    """Run the production Resume Intelligence interpreter (the same
    inputs `resume_ai.service.analyze_resume_version` builds) and return
    the validated `ResumeAIResult` as a dict."""
    from apps.api.services.resume_ai.contracts import ResumeAIResult
    from apps.api.services.resume_ai.interpreter import ResumeAIInterpreter
    from apps.api.services.resume_ai.service import (
        _serialize_deterministic_analysis,
    )

    text = resume.text.strip()
    interpretation = ResumeAIInterpreter(provider).analyze(
        resume_text=text,
        deterministic_analysis=_serialize_deterministic_analysis(
            analyze_resume_deterministically(text)
        ),
    )
    return ResumeAIResult.model_validate(
        {
            **interpretation.result,
            "analysis_version": interpretation.analysis_version,
            "resume_version_id": resume.id,
        }
    ).model_dump(mode="json")
