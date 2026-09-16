from unittest.mock import MagicMock, patch

import pytest

from apps.api.services.resume_ai.providers.openai_provider import (
    OpenAIResumeProvider,
    ProviderAnalysis,
    ResumeAIProviderError,
)


def test_openai_provider_metadata():
    provider = OpenAIResumeProvider(
        api_key="test-key",
        model_name="test-model",
    )

    assert provider.provider_name == "openai"
    assert provider.model_name == "test-model"


@patch(
    "apps.api.services.resume_ai.providers.openai_provider.settings.openai_api_key",
    None,
)
def test_openai_provider_requires_api_key():
    with pytest.raises(ResumeAIProviderError, match="API key"):
        OpenAIResumeProvider(
            api_key=None,
            model_name="test-model",
        )

@patch(
    "apps.api.services.resume_ai.providers.openai_provider.OpenAI"
)
def test_openai_provider_returns_structured_analysis(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    parsed_result = ProviderAnalysis(
        profile={
            "name": "John Doe",
        },
        positioning={
            "apparent_target_role": "AI/ML Engineer",
        },
        sections={},
        skills={
            "demonstrated": ["Python"],
            "skills_only": [],
            "weakly_supported": [],
        },
        experience={
            "bullet_count": 2,
            "achievement_count": 1,
            "responsibility_count": 1,
            "quantified_bullets": 1,
            "findings": [],
        },
        technical_depth={
            "programming": ["Python"],
            "machine_learning": ["scikit-learn"],
            "deep_learning": [],
            "generative_ai": [],
            "cloud": [],
            "mlops": [],
        },
        structure={
            "findings": [],
        },
        findings=[],
        summary={
            "strengths": ["Clear technical focus"],
            "top_priorities": ["Add more measurable outcomes"],
        },
    )

    mock_response = MagicMock()
    mock_response.output_parsed = parsed_result
    mock_client.responses.parse.return_value = mock_response

    provider = OpenAIResumeProvider(
        api_key="test-key",
        model_name="test-model",
    )

    result = provider.generate_structured_analysis(
        resume_text="John Doe\nAI/ML Engineer\nPython",
        deterministic_analysis={
            "skills": ["python"],
            "quantified_evidence": [],
        },
    )

    assert result["profile"]["name"] == "John Doe"
    assert result["positioning"]["apparent_target_role"] == "AI/ML Engineer"
    assert result["skills"]["demonstrated"] == ["Python"]

    mock_client.responses.parse.assert_called_once()


@patch(
    "apps.api.services.resume_ai.providers.openai_provider.OpenAI"
)
def test_openai_provider_rejects_missing_structured_response(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output_parsed = None
    mock_client.responses.parse.return_value = mock_response

    provider = OpenAIResumeProvider(
        api_key="test-key",
        model_name="test-model",
    )

    with pytest.raises(
        ResumeAIProviderError,
        match="no structured resume analysis",
    ):
        provider.generate_structured_analysis(
            resume_text="Resume text",
            deterministic_analysis={},
        )