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


class ProviderObservation(BaseModel):
    """A single labeled observation, used for fields whose content is
    open-ended (the AI has something to say, but not a fixed set of keys)."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(description="Short label for this observation.")
    value: str = Field(
        description="The evidence-backed observation itself."
    )


class ProviderProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        description=(
            "The candidate's name if it appears in the resume text, "
            "otherwise null."
        ),
    )
    observations: list[ProviderObservation] = Field(
        default_factory=list,
        description=(
            "Notable, evidence-backed observations about who the "
            "candidate appears to be professionally (e.g. contact "
            "completeness, years of visible experience). Do not invent "
            "facts not present in the resume."
        ),
    )


class ProviderPositioning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    apparent_target_role: str | None = None
    apparent_specialization: str | None = None
    apparent_seniority: str | None = None
    positioning_strengths: list[str] = Field(default_factory=list)
    positioning_risks: list[str] = Field(default_factory=list)


class ProviderSections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[ProviderObservation] = Field(
        default_factory=list,
        description=(
            "Evidence-backed observations about the resume's sections "
            "(e.g. missing sections, ordering, or content quality)."
        ),
    )


class ProviderSkills(BaseModel):
    model_config = ConfigDict(extra="forbid")

    demonstrated: list[str] = Field(
        default_factory=list,
        description="Skills with visible evidence of use outside a skills list.",
    )
    skills_only: list[str] = Field(
        default_factory=list,
        description="Skills listed but with no demonstrated evidence elsewhere.",
    )
    weakly_supported: list[str] = Field(
        default_factory=list,
        description="Skills with limited or ambiguous supporting evidence.",
    )


class ProviderExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bullet_count: int = Field(
        description="Total experience bullets found in the resume."
    )
    achievement_count: int = Field(
        description="Bullets that communicate an outcome, not just a duty."
    )
    responsibility_count: int = Field(
        description="Bullets that describe a duty without a stated outcome."
    )
    quantified_bullets: int = Field(
        description="Bullets that contain measurable, quantified evidence."
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Short, evidence-backed findings about experience quality.",
    )


class ProviderTechnicalDepth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    programming: list[str] = Field(default_factory=list)
    machine_learning: list[str] = Field(default_factory=list)
    deep_learning: list[str] = Field(default_factory=list)
    generative_ai: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    mlops: list[str] = Field(default_factory=list)


class ProviderStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[str] = Field(
        default_factory=list,
        description=(
            "Short, evidence-backed findings about structural "
            "consistency and readability."
        ),
    )


class ProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: list[str] = Field(default_factory=list)
    top_priorities: list[str] = Field(default_factory=list)


class ProviderAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProviderProfile = Field(default_factory=ProviderProfile)
    positioning: ProviderPositioning = Field(default_factory=ProviderPositioning)
    sections: ProviderSections = Field(default_factory=ProviderSections)
    skills: ProviderSkills = Field(default_factory=ProviderSkills)
    experience: ProviderExperience
    technical_depth: ProviderTechnicalDepth = Field(
        default_factory=ProviderTechnicalDepth
    )
    structure: ProviderStructure = Field(default_factory=ProviderStructure)
    findings: list[ProviderFinding] = Field(default_factory=list)
    summary: ProviderSummary = Field(default_factory=ProviderSummary)


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
        self.client = OpenAI(api_key=resolved_api_key)

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