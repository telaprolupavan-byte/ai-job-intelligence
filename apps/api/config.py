from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve to the repo-root .env regardless of the process's working directory.
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://localhost/jobintel"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # AI configuration
    ai_provider: str = "openai"
    ai_model: str = "gpt-5.6"
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()