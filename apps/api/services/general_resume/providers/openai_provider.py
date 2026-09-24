from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI
from openai import APIConnectionError
from openai import APIError
from openai import APITimeoutError
from openai import AuthenticationError
from pydantic import BaseModel, ConfigDict

from apps.api.config import settings
from apps.api.services.general_resume.prompts import (
    SYSTEM_PROMPT,
    build_general_resume_prompt,
)


# Closed, explicit schema, per the Structured Outputs (strict mode)
# convention the other providers follow. Deliberately narrow: the AI can
# only return explanation text for an improvement that already exists.
# It cannot return a score, a type, a new improvement, or resume text.


class ProviderImprovementItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    improvement_id: str
    explanation: str
    explanation_evidence: str
    guidance: str


class ProviderImprovementExplanations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProviderImprovementItem]


logger = logging.getLogger(__name__)


class GeneralResumeProviderError(RuntimeError):
    """Safe application-level error for General Resume AI provider
    failures."""


class OpenAIGeneralResumeProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        resolved_api_key = api_key or settings.openai_api_key

        if not resolved_api_key:
            raise GeneralResumeProviderError(
                "OpenAI API key is not configured."
            )

        self.model_name = model_name or settings.ai_model
        # Bounded like the other interactive AI providers (AJI-026).
        self.client = OpenAI(
            api_key=resolved_api_key,
            timeout=60.0,
        )

    def generate_improvement_explanations(
        self,
        *,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        user_prompt = build_general_resume_prompt(items=items)

        try:
            response = self.client.responses.parse(
                model=self.model_name,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                text_format=ProviderImprovementExplanations,
            )
        except AuthenticationError as exc:
            logger.error("OpenAI authentication failed: %s", exc)
            raise GeneralResumeProviderError(
                "OpenAI authentication failed."
            ) from exc
        except APITimeoutError as exc:
            logger.error("OpenAI request timed out: %s", exc)
            raise GeneralResumeProviderError(
                "OpenAI request timed out."
            ) from exc
        except APIConnectionError as exc:
            logger.error("Could not connect to OpenAI: %s", exc)
            raise GeneralResumeProviderError(
                "Could not connect to OpenAI."
            ) from exc
        except APIError as exc:
            logger.error("OpenAI API request failed: %s", exc)
            raise GeneralResumeProviderError(
                "OpenAI API request failed."
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected General Resume provider error.")
            raise GeneralResumeProviderError(
                "Unexpected General Resume provider error."
            ) from exc

        parsed = response.output_parsed

        if parsed is None:
            logger.error(
                "OpenAI returned no structured improvement explanations "
                "(refusal or empty output)."
            )
            raise GeneralResumeProviderError(
                "OpenAI returned no structured improvement explanations."
            )

        return parsed.model_dump()
