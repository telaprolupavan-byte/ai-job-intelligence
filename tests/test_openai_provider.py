from unittest.mock import MagicMock, patch

import pytest

from apps.api.services.resume_ai.providers.openai_provider import (
    OpenAIResumeProvider,
    ProviderAnalysis,
    ResumeAIProviderError,
)


def test_provider_analysis_schema_is_openai_strict_compatible():
    """Guards against the invalid_json_schema regression: every object in
    the ProviderAnalysis schema must disallow additional properties and
    mark every declared property as required, exactly as OpenAI's
    Structured Outputs "strict" mode enforces it. A bare `dict[str, Any]`
    field would fail this check because it serializes with
    `additionalProperties: true`, which OpenAI rejects.
    """
    from openai.lib._pydantic import to_strict_json_schema

    schema = to_strict_json_schema(ProviderAnalysis)

    def check(node, path=()):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, (
                    f"additionalProperties must be false at {path}"
                )
                properties = node.get("properties", {})
                required = node.get("required", [])
                assert set(properties.keys()) == set(required), (
                    f"every property must be required at {path}"
                )
            for key, value in node.items():
                check(value, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                check(value, path + (str(index),))

    check(schema)


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
        review={
            "strengths": ["Clear technical focus"],
            "weaknesses": [],
            "findings": [],
            "suggestions": ["Add more measurable outcomes"],
        },
        decoding={
            "professional_profile": "AI/ML Engineer",
            "technical_profile": "Python-focused",
            "work_history": [],
            "education": [],
            "certifications": [],
            "projects": [],
            "skills": [
                {
                    "skill": "Python",
                    "evidence": "Used across experience bullets.",
                    "demonstrated": True,
                }
            ],
            "domains": [],
        },
        position_identification={
            "primary_roles": [
                {
                    "role": "AI/ML Engineer",
                    "rationale": "Experience demonstrates ML model work in Python.",
                }
            ],
            "secondary_roles": [],
            "adjacent_roles": [],
            "supporting_evidence": [],
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

    assert result["decoding"]["professional_profile"] == "AI/ML Engineer"
    assert (
        result["position_identification"]["primary_roles"][0]["role"]
        == "AI/ML Engineer"
    )
    assert result["decoding"]["skills"][0]["skill"] == "Python"

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