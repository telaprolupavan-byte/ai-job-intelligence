from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


PROMPT_VERSION = "1.0"


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_requirement_semantics(
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


class RequirementIntelligenceInterpreter:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        *,
        raw_jd_text: str,
        deterministic_context: dict[str, Any],
    ) -> AIInterpretation:
        result = self.provider.generate_requirement_semantics(
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
