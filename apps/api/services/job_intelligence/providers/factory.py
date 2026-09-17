from apps.api.config import settings
from apps.api.services.job_intelligence.providers.openai_provider import (
    JobIntelligenceProviderError,
    OpenAIJobIntelligenceProvider,
)


def create_job_intelligence_provider():
    provider = settings.ai_provider.lower().strip()

    if provider == "openai":
        return OpenAIJobIntelligenceProvider()

    raise JobIntelligenceProviderError(
        f"Unsupported AI provider: {provider}"
    )
