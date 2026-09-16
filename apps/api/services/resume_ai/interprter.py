from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


ANALYSIS_VERSION = "1.0"
PROMPT_VERSION = "1.0"
INTERPRETER_VERSION = "1.0"


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_structured_analysis(
        self,
        *,
        resume_text: str,
        deterministic_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        ...


@dataclass
class AIInterpretation:
    analysis_version: str
    interpreter_version: str
    prompt_version: str
    provider: str
    model: str
    result: dict[str, Any]


class ResumeAIInterpreter:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        *,
        resume_text: str,
        deterministic_analysis: dict[str, Any],
    ) -> AIInterpretation:
        result = self.provider.generate_structured_analysis(
            resume_text=resume_text,
            deterministic_analysis=deterministic_analysis,
        )

        return AIInterpretation(
            analysis_version=ANALYSIS_VERSION,
            interpreter_version=INTERPRETER_VERSION,
            prompt_version=PROMPT_VERSION,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            result=result,
        )