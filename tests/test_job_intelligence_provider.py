from unittest.mock import MagicMock, patch

import pytest

from apps.api.services.job_intelligence.providers.openai_provider import (
    JobIntelligenceProviderError,
    OpenAIJobIntelligenceProvider,
    ProviderJobSemantics,
)


def test_provider_job_semantics_schema_is_openai_strict_compatible():
    """Guards against the invalid_json_schema regression the resume AI
    provider already tests for: every object in the schema must disallow
    additional properties and mark every declared property as required.
    """
    from openai.lib._pydantic import to_strict_json_schema

    schema = to_strict_json_schema(ProviderJobSemantics)

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


def test_provider_metadata():
    provider = OpenAIJobIntelligenceProvider(
        api_key="test-key",
        model_name="test-model",
    )

    assert provider.provider_name == "openai"
    assert provider.model_name == "test-model"


@patch(
    "apps.api.services.job_intelligence.providers.openai_provider.settings.openai_api_key",
    None,
)
def test_provider_requires_api_key():
    with pytest.raises(JobIntelligenceProviderError, match="API key"):
        OpenAIJobIntelligenceProvider(
            api_key=None,
            model_name="test-model",
        )


@patch("apps.api.services.job_intelligence.providers.openai_provider.OpenAI")
def test_provider_returns_structured_semantics(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    parsed_result = ProviderJobSemantics(
        normalized_title="Machine Learning Engineer",
        normalized_title_evidence="ML Engineer II",
        normalized_title_confidence="high",
        role_family="Machine Learning Engineering",
        role_family_evidence="ML Engineer II",
        role_family_confidence="medium",
        seniority=None,
        domain="Generative AI",
        domain_evidence="building GenAI products",
        domain_confidence="medium",
    )

    mock_response = MagicMock()
    mock_response.output_parsed = parsed_result
    mock_client.responses.parse.return_value = mock_response

    provider = OpenAIJobIntelligenceProvider(
        api_key="test-key",
        model_name="test-model",
    )

    result = provider.generate_job_semantics(
        raw_jd_text="ML Engineer II. We are building GenAI products.",
        deterministic_context={"employment_type": "full_time"},
    )

    assert result["normalized_title"] == "Machine Learning Engineer"
    assert result["domain"] == "Generative AI"
    mock_client.responses.parse.assert_called_once()


@patch("apps.api.services.job_intelligence.providers.openai_provider.OpenAI")
def test_provider_rejects_missing_structured_response(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output_parsed = None
    mock_client.responses.parse.return_value = mock_response

    provider = OpenAIJobIntelligenceProvider(
        api_key="test-key",
        model_name="test-model",
    )

    with pytest.raises(
        JobIntelligenceProviderError,
        match="no structured Job Intelligence semantics",
    ):
        provider.generate_job_semantics(
            raw_jd_text="Job description",
            deterministic_context={},
        )
