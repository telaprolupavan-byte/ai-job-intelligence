from apps.api.services.resume_ai.interpreter import (
    ResumeAIInterpreter,
)


class FakeAIProvider:
    provider_name = "test"
    model_name = "fake-model"

    def generate_structured_analysis(
        self,
        *,
        resume_text,
        deterministic_analysis,
    ):
        return {
            "findings": [
                {
                    "category": "experience",
                    "priority": "high",
                    "finding": "Several experience bullets lack measurable outcomes.",
                    "evidence": "The deterministic analysis identified bullets without quantified evidence.",
                    "impact": "The resume may communicate responsibilities more strongly than measurable impact.",
                    "recommendation": "Where truthful, add measurable outcomes.",
                    "confidence": "high",
                }
            ]
        }


def test_resume_ai_interpreter():
    interpreter = ResumeAIInterpreter(FakeAIProvider())

    result = interpreter.analyze(
        resume_text="AI/ML Engineer with Python experience.",
        deterministic_analysis={
            "skills": ["python"],
            "quantified_evidence": [],
        },
    )

    assert result.provider == "test"
    assert result.model == "fake-model"
    assert result.analysis_version == "1.0"
    assert len(result.result["findings"]) == 1


def test_resume_ai_interpreter_rejects_malformed_findings():
    class MalformedProvider(FakeAIProvider):
        def generate_structured_analysis(
            self,
            *,
            resume_text,
            deterministic_analysis,
        ):
            return {"findings": [{"category": "experience"}]}

    interpreter = ResumeAIInterpreter(MalformedProvider())

    try:
        interpreter.analyze(
            resume_text="Resume",
            deterministic_analysis={},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Malformed AI findings should be rejected")