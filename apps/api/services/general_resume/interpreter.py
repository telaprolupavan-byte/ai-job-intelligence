from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


PROMPT_VERSION = "1.0"


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_improvement_explanations(
        self,
        *,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ...


@dataclass
class AIInterpretation:
    prompt_version: str
    provider: str
    model: str
    result: dict[str, Any]


class GeneralResumeInterpreter:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def explain(self, *, items: list[dict[str, Any]]) -> AIInterpretation:
        result = self.provider.generate_improvement_explanations(items=items)

        if not isinstance(result, dict):
            raise ValueError("AI provider must return a structured object.")

        if not isinstance(result.get("items", []), list):
            raise ValueError("AI provider items must be a list.")

        return AIInterpretation(
            prompt_version=PROMPT_VERSION,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            result=result,
        )
