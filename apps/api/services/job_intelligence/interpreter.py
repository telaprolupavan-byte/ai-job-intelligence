from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


# 1.1 (AJI-022): added CRITICAL RULE 6 (JD text is data, never
# instructions) - users can now paste arbitrary job content straight into
# this pipeline.
PROMPT_VERSION = "1.1"


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_job_semantics(
        self,
        *,
        raw_jd_text: str,
        deterministic_context: dict[str, Any],
    ) -> dict[str, Any]:
        ...


@dataclass
class AIInterpretation:
    prompt_version: str
    provider: str
    model: str
    result: dict[str, Any]


class JobIntelligenceInterpreter:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        *,
        raw_jd_text: str,
        deterministic_context: dict[str, Any],
    ) -> AIInterpretation:
        result = self.provider.generate_job_semantics(
            raw_jd_text=raw_jd_text,
            deterministic_context=deterministic_context,
        )

        if not isinstance(result, dict):
            raise ValueError("AI provider must return a structured object.")

        return AIInterpretation(
            prompt_version=PROMPT_VERSION,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            result=result,
        )
