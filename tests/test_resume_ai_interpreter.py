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
            "review": {
                "strengths": [],
                "weaknesses": [],
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
                ],
                "suggestions": [],
            },
            "decoding": {
                "professional_profile": None,
                "technical_profile": None,
                "work_history": [],
                "education": [],
                "certifications": [],
                "projects": [],
                "skills": [],
                "domains": [],
            },
            "position_identification": {
                "primary_roles": [],
                "secondary_roles": [],
                "adjacent_roles": [],
                "supporting_evidence": [],
            },
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
    assert result.analysis_version == "2.0"
    assert len(result.result["review"]["findings"]) == 1


def test_resume_ai_interpreter_rejects_malformed_findings():
    class MalformedProvider(FakeAIProvider):
        def generate_structured_analysis(
            self,
            *,
            resume_text,
            deterministic_analysis,
        ):
            return {"review": {"findings": [{"category": "experience"}]}}

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


def test_resume_ai_interpreter_rejects_missing_review():
    class NoReviewProvider(FakeAIProvider):
        def generate_structured_analysis(
            self,
            *,
            resume_text,
            deterministic_analysis,
        ):
            return {"decoding": {}, "position_identification": {}}

    interpreter = ResumeAIInterpreter(NoReviewProvider())

    try:
        interpreter.analyze(
            resume_text="Resume",
            deterministic_analysis={},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Missing review section should be rejected")
