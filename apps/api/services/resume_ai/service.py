from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from apps.api.models import ResumeAIAnalysis, ResumeVersion
from apps.api.services.resume_ai.contracts import ResumeAIResult
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from apps.api.services.resume_ai.interpreter import (
    ANALYSIS_VERSION,
    PROMPT_VERSION,
    ResumeAIInterpreter,
)
from apps.api.services.resume_ai.providers import create_resume_ai_provider


ANALYZER_VERSION = "1.0"

logger = logging.getLogger(__name__)


class ResumeAIServiceError(RuntimeError):
    """Application-level error for resume AI analysis failures."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def _serialize_deterministic_analysis(
    analysis: Any,
) -> dict[str, Any]:
    return {
        "word_count": analysis.word_count,
        "character_count": analysis.character_count,
        "emails": analysis.emails,
        "phones": analysis.phones,
        "urls": analysis.urls,
        "sections": [
            {
                "name": section.name,
                "heading": section.heading,
                "start_line": section.start_line,
                "end_line": section.end_line,
            }
            for section in analysis.sections
        ],
        "bullets": [
            {
                "text": bullet.text,
                "section": bullet.section,
                "has_action_verb": bullet.has_action_verb,
                "action_verb": bullet.action_verb,
                "has_quantification": bullet.has_quantification,
                "quantified_evidence": bullet.quantified_evidence,
                "weak_phrases": bullet.weak_phrases,
                "word_count": bullet.word_count,
            }
            for bullet in analysis.bullets
        ],
        "quantified_evidence": analysis.quantified_evidence,
        "weak_language": analysis.weak_language,
        "repeated_phrases": analysis.repeated_phrases,
        "skills": analysis.skills,
        "skill_evidence": analysis.skill_evidence,
        "structural_findings": analysis.structural_findings,
        "technical_signals": analysis.technical_signals,
        "project_signals": analysis.project_signals,
        "career_signals": analysis.career_signals,
    }


def analyze_resume_version(
    *,
    db: Session,
    user_id: UUID,
    resume_version_id: UUID,
) -> ResumeAIResult:
    resume_version = (
        db.query(ResumeVersion)
        .join(ResumeVersion.resume)
        .filter(
            ResumeVersion.id == resume_version_id,
            ResumeVersion.resume.has(user_id=user_id),
        )
        .first()
    )

    if resume_version is None:
        raise ResumeAIServiceError(
            "Resume version not found.",
            status_code=404,
        )

    # Reuse a valid, already-computed analysis for the exact same
    # ResumeVersion + analyzer/prompt pipeline instead of re-calling the
    # AI provider on every click. Resume content is immutable per
    # version, so a cached analysis for this exact pipeline is still
    # valid indefinitely.
    cached_analysis = (
        db.query(ResumeAIAnalysis)
        .filter(
            ResumeAIAnalysis.resume_version_id == resume_version_id,
            ResumeAIAnalysis.user_id == user_id,
            ResumeAIAnalysis.analysis_version == ANALYSIS_VERSION,
            ResumeAIAnalysis.analyzer_version == ANALYZER_VERSION,
            ResumeAIAnalysis.prompt_version == PROMPT_VERSION,
        )
        .order_by(ResumeAIAnalysis.created_at.desc())
        .first()
    )

    if cached_analysis is not None:
        return ResumeAIResult.model_validate(cached_analysis.analysis_result)

    resume_text = resume_version.content_text.strip()

    if not resume_text:
        raise ResumeAIServiceError(
            "Resume version contains no readable text.",
            status_code=422,
        )

    deterministic_analysis = analyze_resume_deterministically(
        resume_text
    )

    deterministic_payload = _serialize_deterministic_analysis(
        deterministic_analysis
    )

    try:
        provider = create_resume_ai_provider()
        interpreter = ResumeAIInterpreter(provider)
        interpretation = interpreter.analyze(
            resume_text=resume_text,
            deterministic_analysis=deterministic_payload,
        )
        result_payload = {
            **interpretation.result,
            "analysis_version": interpretation.analysis_version,
            "resume_version_id": str(resume_version_id),
        }
        result = ResumeAIResult.model_validate(result_payload)
    except (ValidationError, RuntimeError, ValueError) as exc:
        db.rollback()
        logger.error(
            "Resume AI analysis failed for resume_version_id=%s: %s",
            resume_version_id,
            exc,
        )
        raise ResumeAIServiceError(
            "Unable to generate a valid resume AI analysis.",
            status_code=503,
        ) from exc

    analysis_record = ResumeAIAnalysis(
        user_id=user_id,
        resume_version_id=resume_version_id,
        analysis_version=interpretation.analysis_version,
        analyzer_version=ANALYZER_VERSION,
        model_provider=interpretation.provider,
        model_name=interpretation.model,
        prompt_version=interpretation.prompt_version,
        analysis_result=result.model_dump(mode="json"),
    )

    db.add(analysis_record)
    db.commit()
    db.refresh(analysis_record)

    return result