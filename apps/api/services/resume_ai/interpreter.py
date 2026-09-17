from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import ResumeFinding


ANALYSIS_VERSION = "2.0"
PROMPT_VERSION = "2.0"
INTERPRETER_VERSION = "2.0"


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

        if not isinstance(result, dict):
            raise ValueError("AI provider must return a structured object.")

        review = result.get("review")
        if not isinstance(review, dict):
            raise ValueError("AI provider must return a review section.")

        findings = review.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("AI provider review findings must be a list.")

        for finding in findings:
            ResumeFinding.model_validate(finding)

        return AIInterpretation(
            analysis_version=ANALYSIS_VERSION,
            interpreter_version=INTERPRETER_VERSION,
            prompt_version=PROMPT_VERSION,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            result=result,
        )
