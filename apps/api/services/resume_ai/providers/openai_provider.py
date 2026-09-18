from __future__ import annotations

import logging
from typing import Any, Literal

from openai import OpenAI
from openai import APIConnectionError
from openai import APIError
from openai import APITimeoutError
from openai import AuthenticationError
from pydantic import BaseModel, ConfigDict, Field

from apps.api.config import settings
from apps.api.services.resume_ai.prompts import (
    SYSTEM_PROMPT,
    build_analysis_prompt,
)


# OpenAI Structured Outputs (strict mode) requires every object in the
# response schema to be closed: `additionalProperties: false` and every
# declared property present in `required`. A bare `dict[str, Any]` field
# instead produces `additionalProperties: true`, which OpenAI rejects
# (`invalid_json_schema`). Each field below is therefore modeled with an
# explicit, closed schema rather than an open-ended dict.


class ProviderFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    priority: Literal["high", "medium", "low"]
    finding: str
    evidence: str
    impact: str
    recommendation: str
    confidence: Literal["high", "medium", "low"]


class ProviderReview(BaseModel):
    """Resume Review: feedback on the resume as written."""

    model_config = ConfigDict(extra="forbid")

    strengths: list[str] = Field(
        default_factory=list,
        description="Evidence-backed strengths of the resume as written.",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Evidence-backed weaknesses of the resume as written.",
    )
    findings: list[ProviderFinding] = Field(default_factory=list)
    suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable, truthful suggestions for improving the resume.",
    )


class ProviderSkillEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    evidence: str = Field(
        description=(
            "Where and how this skill is evidenced in the resume, or a "
            "note that it only appears in a skills list."
        )
    )
    demonstrated: bool = Field(
        description="Whether the skill has visible evidence of use, not just a listing."
    )


class ProviderWorkHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    title: str | None = None
    duration: str | None = None
    summary: str | None = None


class ProviderEducationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str | None = None
    credential: str | None = None
    field_of_study: str | None = None
    graduation: str | None = None


class ProviderProjectEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)


class ProviderDecoding(BaseModel):
    """Resume Decoding: what the resume says about the candidate."""

    model_config = ConfigDict(extra="forbid")

    professional_profile: str | None = Field(
        default=None,
        description="A short, evidence-backed summary of who the candidate appears to be professionally.",
    )
    technical_profile: str | None = Field(
        default=None,
        description="A short, evidence-backed summary of the candidate's technical profile.",
    )
    work_history: list[ProviderWorkHistoryEntry] = Field(default_factory=list)
    education: list[ProviderEducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[ProviderProjectEntry] = Field(default_factory=list)
    skills: list[ProviderSkillEvidence] = Field(default_factory=list)
    domains: list[str] = Field(
        default_factory=list,
        description="Industry or problem domains the resume provides evidence for.",
    )


class ProviderRoleMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    rationale: str = Field(
        description="Why the resume's evidence supports this role."
    )


class ProviderPositionIdentification(BaseModel):
    """Position Identification: which roles the resume's evidence supports."""

    model_config = ConfigDict(extra="forbid")

    primary_roles: list[ProviderRoleMatch] = Field(
        default_factory=list,
        description="Roles the resume most strongly and directly supports.",
    )
    secondary_roles: list[ProviderRoleMatch] = Field(
        default_factory=list,
        description="Roles the resume reasonably supports, but less strongly than the primary roles.",
    )
    adjacent_roles: list[ProviderRoleMatch] = Field(
        default_factory=list,
        description="Related roles the resume provides partial or transferable evidence for.",
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence points from the resume that ground the identified roles.",
    )


class ProviderAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review: ProviderReview
    decoding: ProviderDecoding
    position_identification: ProviderPositionIdentification


logger = logging.getLogger(__name__)


class ResumeAIProviderError(RuntimeError):
    """Safe application-level error for resume AI provider failures."""


class OpenAIResumeProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        resolved_api_key = api_key or settings.openai_api_key

        if not resolved_api_key:
            raise ResumeAIProviderError(
                "OpenAI API key is not configured."
            )

        self.model_name = model_name or settings.ai_model

        # Without an explicit timeout, the SDK's default (10 minutes) lets
        # a stalled connection (e.g. a network/proxy issue between this
        # service and OpenAI) leave the "Analyze Resume" request - and the
        # frontend's loading state - hanging far longer than any
        # interactive UI should. A bounded timeout instead surfaces
        # APITimeoutError/APIConnectionError quickly through the existing
        # error handling below, as a clear, actionable failure.
        self.client = OpenAI(
            api_key=resolved_api_key,
            timeout=60.0,
            max_retries=1,
        )

    def generate_structured_analysis(
        self,
        *,
        resume_text: str,
        deterministic_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        user_prompt = build_analysis_prompt(
            resume_text=resume_text,
            deterministic_analysis=deterministic_analysis,
        )

        try:
            response = self.client.responses.parse(
                model=self.model_name,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                text_format=ProviderAnalysis,
            )
        except AuthenticationError as exc:
            logger.error("OpenAI authentication failed: %s", exc)
            raise ResumeAIProviderError(
                "OpenAI authentication failed."
            ) from exc
        except APITimeoutError as exc:
            logger.error("OpenAI request timed out: %s", exc)
            raise ResumeAIProviderError(
                "OpenAI request timed out."
            ) from exc
        except APIConnectionError as exc:
            logger.error("Could not connect to OpenAI: %s", exc)
            raise ResumeAIProviderError(
                "Could not connect to OpenAI."
            ) from exc
        except APIError as exc:
            logger.error("OpenAI API request failed: %s", exc)
            raise ResumeAIProviderError(
                "OpenAI API request failed."
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected resume AI provider error.")
            raise ResumeAIProviderError(
                "Unexpected resume AI provider error."
            ) from exc

        parsed = response.output_parsed

        if parsed is None:
            logger.error(
                "OpenAI returned no structured resume analysis "
                "(refusal or empty output)."
            )
            raise ResumeAIProviderError(
                "OpenAI returned no structured resume analysis."
            )

        return parsed.model_dump()