from apps.api.config import settings
from apps.api.services.resume_ai.providers.openai_provider import (
    OpenAIResumeProvider,
    ResumeAIProviderError,
)


def create_resume_ai_provider():
    provider = settings.ai_provider.lower().strip()

    if provider == "openai":
        return OpenAIResumeProvider()

    raise ResumeAIProviderError(
        f"Unsupported AI provider: {provider}"
    )