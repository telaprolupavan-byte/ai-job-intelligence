from __future__ import annotations

import logging
from typing import Any, Literal

from openai import OpenAI
from openai import APIConnectionError
from openai import APIError
from openai import APITimeoutError
from openai import AuthenticationError
from pydantic import BaseModel, ConfigDict

from apps.api.config import settings
from apps.api.services.gap_analysis.prompts import (
    SYSTEM_PROMPT,
    build_gap_suggestions_prompt,
)


# See apps/api/services/resume_ai/providers/openai_provider.py for why
# every field below is a closed, explicit schema rather than a bare
# `dict[str, Any]`: OpenAI Structured Outputs (strict mode) requires
# `additionalProperties: false` and every declared property in
# `required` on every object in the schema.


ConfidenceLiteral = Literal["high", "medium", "low"]


class ProviderGapItem(BaseModel):
    """One AI-produced gap explanation/suggestion pair. Deliberately
    narrow: the requirement's identity, status, and evidence are already
    known (see contracts.py) — the AI only ever contributes explanation
    text, a verbatim evidence quote for that explanation (checked against
    the source text by the validator before being trusted), and a
    suggestion. It never re-declares status, category, or
    suggestion_type — those are computed deterministically and enforced
    by the validator regardless of what the AI returns.
    """

    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    explanation: str
    explanation_evidence: str
    suggestion_text: str
    confidence: ConfidenceLiteral


class ProviderGapAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gaps: list[ProviderGapItem]


logger = logging.getLogger(__name__)


class GapAnalysisProviderError(RuntimeError):
    """Safe application-level error for Gap Analysis AI provider failures."""


class OpenAIGapAnalysisProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        resolved_api_key = api_key or settings.openai_api_key

        if not resolved_api_key:
            raise GapAnalysisProviderError(
                "OpenAI API key is not configured."
            )

        self.model_name = model_name or settings.ai_model
        self.client = OpenAI(api_key=resolved_api_key)

    def generate_gap_suggestions(
        self,
        *,
        gap_candidates: list[dict[str, Any]],
        job_context: dict[str, Any],
    ) -> dict[str, Any]:
        user_prompt = build_gap_suggestions_prompt(
            gap_candidates=gap_candidates,
            job_context=job_context,
        )

        try:
            response = self.client.responses.parse(
                model=self.model_name,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                text_format=ProviderGapAnalysis,
            )
        except AuthenticationError as exc:
            logger.error("OpenAI authentication failed: %s", exc)
            raise GapAnalysisProviderError(
                "OpenAI authentication failed."
            ) from exc
        except APITimeoutError as exc:
            logger.error("OpenAI request timed out: %s", exc)
            raise GapAnalysisProviderError(
                "OpenAI request timed out."
            ) from exc
        except APIConnectionError as exc:
            logger.error("Could not connect to OpenAI: %s", exc)
            raise GapAnalysisProviderError(
                "Could not connect to OpenAI."
            ) from exc
        except APIError as exc:
            logger.error("OpenAI API request failed: %s", exc)
            raise GapAnalysisProviderError(
                "OpenAI API request failed."
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected Gap Analysis provider error.")
            raise GapAnalysisProviderError(
                "Unexpected Gap Analysis provider error."
            ) from exc

        parsed = response.output_parsed

        if parsed is None:
            logger.error(
                "OpenAI returned no structured Gap Analysis suggestions "
                "(refusal or empty output)."
            )
            raise GapAnalysisProviderError(
                "OpenAI returned no structured Gap Analysis suggestions."
            )

        return parsed.model_dump()
