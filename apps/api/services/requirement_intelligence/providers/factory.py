from apps.api.config import settings
from apps.api.services.requirement_intelligence.providers.openai_provider import (
    OpenAIRequirementIntelligenceProvider,
    RequirementIntelligenceProviderError,
)


def create_requirement_intelligence_provider():
    provider = settings.ai_provider.lower().strip()

    if provider == "openai":
        return OpenAIRequirementIntelligenceProvider()

    raise RequirementIntelligenceProviderError(
        f"Unsupported AI provider: {provider}"
    )
