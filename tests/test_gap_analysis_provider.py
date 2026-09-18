"""Tests for the Gap Analysis (AJI-015) OpenAI provider
(apps/api/services/gap_analysis/providers/openai_provider.py), mirroring
tests/test_job_intelligence_provider.py's conventions.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from apps.api.services.gap_analysis.providers.openai_provider import (
    GapAnalysisProviderError,
    OpenAIGapAnalysisProvider,
    ProviderGapAnalysis,
    ProviderGapItem,
)


def test_provider_gap_analysis_schema_is_openai_strict_compatible():
    """Guards against the invalid_json_schema regression the resume AI
    and Job Intelligence providers already test for: every object in the
    schema must disallow additional properties and mark every declared
    property as required.
    """
    from openai.lib._pydantic import to_strict_json_schema

    schema = to_strict_json_schema(ProviderGapAnalysis)

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
    provider = OpenAIGapAnalysisProvider(
        api_key="test-key",
        model_name="test-model",
    )

    assert provider.provider_name == "openai"
    assert provider.model_name == "test-model"


@patch(
    "apps.api.services.gap_analysis.providers.openai_provider.settings.openai_api_key",
    None,
)
def test_provider_requires_api_key():
    with pytest.raises(GapAnalysisProviderError, match="API key"):
        OpenAIGapAnalysisProvider(
            api_key=None,
            model_name="test-model",
        )


@patch("apps.api.services.gap_analysis.providers.openai_provider.OpenAI")
def test_provider_returns_structured_gaps(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    parsed_result = ProviderGapAnalysis(
        gaps=[
            ProviderGapItem(
                requirement_id="skill:rust",
                explanation="No Rust evidence in the resume.",
                explanation_evidence="5+ years of Rust required.",
                suggestion_text="If you have Rust experience, add it.",
                confidence="high",
            )
        ]
    )

    mock_response = MagicMock()
    mock_response.output_parsed = parsed_result
    mock_client.responses.parse.return_value = mock_response

    provider = OpenAIGapAnalysisProvider(
        api_key="test-key",
        model_name="test-model",
    )

    result = provider.generate_gap_suggestions(
        gap_candidates=[
            {
                "requirement_id": "skill:rust",
                "status": "missing",
                "jd_evidence": "5+ years of Rust required.",
            }
        ],
        job_context={"job_id": "job-1"},
    )

    assert result["gaps"][0]["requirement_id"] == "skill:rust"
    mock_client.responses.parse.assert_called_once()


@patch("apps.api.services.gap_analysis.providers.openai_provider.OpenAI")
def test_provider_rejects_missing_structured_response(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output_parsed = None
    mock_client.responses.parse.return_value = mock_response

    provider = OpenAIGapAnalysisProvider(
        api_key="test-key",
        model_name="test-model",
    )

    with pytest.raises(
        GapAnalysisProviderError,
        match="no structured Gap Analysis suggestions",
    ):
        provider.generate_gap_suggestions(
            gap_candidates=[],
            job_context={},
        )


@patch("apps.api.services.gap_analysis.providers.openai_provider.OpenAI")
def test_provider_wraps_authentication_error(mock_openai):
    from openai import AuthenticationError

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.responses.parse.side_effect = AuthenticationError(
        "bad key", response=MagicMock(status_code=401), body=None
    )

    provider = OpenAIGapAnalysisProvider(
        api_key="test-key",
        model_name="test-model",
    )

    with pytest.raises(GapAnalysisProviderError, match="authentication failed"):
        provider.generate_gap_suggestions(gap_candidates=[], job_context={})


@patch("apps.api.services.gap_analysis.providers.openai_provider.OpenAI")
def test_provider_wraps_timeout_error(mock_openai):
    from openai import APITimeoutError

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.responses.parse.side_effect = APITimeoutError(request=MagicMock())

    provider = OpenAIGapAnalysisProvider(api_key="test-key", model_name="test-model")

    with pytest.raises(GapAnalysisProviderError, match="timed out"):
        provider.generate_gap_suggestions(gap_candidates=[], job_context={})


@patch("apps.api.services.gap_analysis.providers.openai_provider.OpenAI")
def test_provider_wraps_connection_error(mock_openai):
    from openai import APIConnectionError

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.responses.parse.side_effect = APIConnectionError(request=MagicMock())

    provider = OpenAIGapAnalysisProvider(api_key="test-key", model_name="test-model")

    with pytest.raises(GapAnalysisProviderError, match="Could not connect"):
        provider.generate_gap_suggestions(gap_candidates=[], job_context={})


@patch("apps.api.services.gap_analysis.providers.openai_provider.OpenAI")
def test_provider_wraps_generic_api_error(mock_openai):
    from openai import APIError

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.responses.parse.side_effect = APIError(
        "server error", MagicMock(), body=None
    )

    provider = OpenAIGapAnalysisProvider(api_key="test-key", model_name="test-model")

    with pytest.raises(GapAnalysisProviderError, match="OpenAI API request failed"):
        provider.generate_gap_suggestions(gap_candidates=[], job_context={})


@patch("apps.api.services.gap_analysis.providers.openai_provider.OpenAI")
def test_provider_wraps_malformed_output_as_safe_error(mock_openai):
    """A raw schema-validation failure from the SDK must not escape as-is
    — it is caught by the generic handler and re-raised as the safe,
    application-level error type."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.responses.parse.side_effect = ValidationError.from_exception_data(
        "ProviderGapAnalysis", []
    )

    provider = OpenAIGapAnalysisProvider(api_key="test-key", model_name="test-model")

    with pytest.raises(
        GapAnalysisProviderError, match="Unexpected Gap Analysis provider error"
    ):
        provider.generate_gap_suggestions(gap_candidates=[], job_context={})
