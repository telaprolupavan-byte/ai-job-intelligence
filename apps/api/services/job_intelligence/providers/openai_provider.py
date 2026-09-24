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
from apps.api.services.job_intelligence.prompts import (
    SYSTEM_PROMPT,
    build_job_semantics_prompt,
)


# See apps/api/services/resume_ai/providers/openai_provider.py for why
# every field below is a closed, explicit schema rather than a bare
# `dict[str, Any]`: OpenAI Structured Outputs (strict mode) requires
# `additionalProperties: false` and every declared property in
# `required` on every object in the schema.


ConfidenceLiteral = Literal["high", "medium", "low"]


class ProviderJobSemantics(BaseModel):
    """The AI semantic decoding stage's entire output.

    Deliberately narrow: deterministic extraction already owns skills,
    experience, education, certifications, authorization, compensation,
    and location — this stage only decodes normalized_title, role_family,
    seniority, and domain, each with verbatim evidence checked against
    the source text by the validator before being trusted.
    """

    model_config = ConfigDict(extra="forbid")

    normalized_title: str | None = None
    normalized_title_evidence: str | None = None
    normalized_title_confidence: ConfidenceLiteral | None = None

    role_family: str | None = None
    role_family_evidence: str | None = None
    role_family_confidence: ConfidenceLiteral | None = None

    seniority: str | None = None
    seniority_evidence: str | None = None
    seniority_confidence: ConfidenceLiteral | None = None

    domain: str | None = None
    domain_evidence: str | None = None
    domain_confidence: ConfidenceLiteral | None = None


logger = logging.getLogger(__name__)


class JobIntelligenceProviderError(RuntimeError):
    """Safe application-level error for Job Intelligence AI provider failures."""


class OpenAIJobIntelligenceProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        resolved_api_key = api_key or settings.openai_api_key

        if not resolved_api_key:
            raise JobIntelligenceProviderError(
                "OpenAI API key is not configured."
            )

        self.model_name = model_name or settings.ai_model
        # Bounded like the Resume Intelligence provider: the SDK's
        # default timeout (10 minutes) would let a stalled connection
        # hold this interactive request open long after the UI gave up.
        self.client = OpenAI(
            api_key=resolved_api_key,
            timeout=60.0,
        )

    def generate_job_semantics(
        self,
        *,
        raw_jd_text: str,
        deterministic_context: dict[str, Any],
    ) -> dict[str, Any]:
        user_prompt = build_job_semantics_prompt(
            raw_jd_text=raw_jd_text,
            deterministic_context=deterministic_context,
        )

        try:
            response = self.client.responses.parse(
                model=self.model_name,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                text_format=ProviderJobSemantics,
            )
        except AuthenticationError as exc:
            logger.error("OpenAI authentication failed: %s", exc)
            raise JobIntelligenceProviderError(
                "OpenAI authentication failed."
            ) from exc
        except APITimeoutError as exc:
            logger.error("OpenAI request timed out: %s", exc)
            raise JobIntelligenceProviderError(
                "OpenAI request timed out."
            ) from exc
        except APIConnectionError as exc:
            logger.error("Could not connect to OpenAI: %s", exc)
            raise JobIntelligenceProviderError(
                "Could not connect to OpenAI."
            ) from exc
        except APIError as exc:
            logger.error("OpenAI API request failed: %s", exc)
            raise JobIntelligenceProviderError(
                "OpenAI API request failed."
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected Job Intelligence provider error.")
            raise JobIntelligenceProviderError(
                "Unexpected Job Intelligence provider error."
            ) from exc

        parsed = response.output_parsed

        if parsed is None:
            logger.error(
                "OpenAI returned no structured Job Intelligence semantics "
                "(refusal or empty output)."
            )
            raise JobIntelligenceProviderError(
                "OpenAI returned no structured Job Intelligence semantics."
            )

        return parsed.model_dump()
