from apps.api.config import settings
from apps.api.services.general_resume.providers.openai_provider import (
    GeneralResumeProviderError,
    OpenAIGeneralResumeProvider,
)


def create_general_resume_provider():
    provider = settings.ai_provider.lower().strip()

    if provider == "openai":
        return OpenAIGeneralResumeProvider()

    raise GeneralResumeProviderError(
        f"Unsupported AI provider: {provider}"
    )
