from __future__ import annotations

from typing import Any, Literal

from openai import OpenAI
from openai import APIConnectionError
from openai import APIError
from openai import APITimeoutError
from openai import AuthenticationError
from pydantic import BaseModel, Field

from apps.api.config import settings
from apps.api.services.resume_ai.prompts import (
    SYSTEM_PROMPT,
    build_analysis_prompt,
)



class ProviderFinding(BaseModel):
    category: str
    priority: Literal["high", "medium", "low"]
    finding: str
    evidence: str
    impact: str
    recommendation: str
    confidence: Literal["high", "medium", "low"]


class ProviderAnalysis(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    positioning: dict[str, Any] = Field(default_factory=dict)
    sections: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, Any] = Field(default_factory=dict)
    experience: dict[str, Any] = Field(default_factory=dict)
    technical_depth: dict[str, Any] = Field(default_factory=dict)
    structure: dict[str, Any] = Field(default_factory=dict)
    findings: list[ProviderFinding] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)



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
            raise ResumeAIProviderError(
                "OpenAI authentication failed."
            ) from exc
        except APITimeoutError as exc:
            raise ResumeAIProviderError(
                "OpenAI request timed out."
            ) from exc
        except APIConnectionError as exc:
            raise ResumeAIProviderError(
                "Could not connect to OpenAI."
            ) from exc
        except APIError as exc:
            raise ResumeAIProviderError(
                "OpenAI API request failed."
            ) from exc
        except Exception as exc:
            raise ResumeAIProviderError(
                "Unexpected resume AI provider error."
            ) from exc

        parsed = response.output_parsed

        if parsed is None:
            raise ResumeAIProviderError(
                "OpenAI returned no structured resume analysis."
            )

        return parsed.model_dump()