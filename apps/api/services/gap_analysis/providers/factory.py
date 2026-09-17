from apps.api.config import settings
from apps.api.services.gap_analysis.providers.openai_provider import (
    GapAnalysisProviderError,
    OpenAIGapAnalysisProvider,
)


def create_gap_analysis_provider():
    provider = settings.ai_provider.lower().strip()

    if provider == "openai":
        return OpenAIGapAnalysisProvider()

    raise GapAnalysisProviderError(
        f"Unsupported AI provider: {provider}"
    )
