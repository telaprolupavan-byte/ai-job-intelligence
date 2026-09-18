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

    # Password reset
    reset_token_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"

    # Email (SMTP). If smtp_host is unset, password reset emails are
    # logged instead of sent, so the feature works without a configured
    # mail provider (e.g. in dev/test).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@ai-job-intelligence.local"
    smtp_use_tls: bool = True

    # Job discovery. Unset by default: which company board(s) to actually
    # ingest is a product/legal decision (whose public postings AJI has
    # permission to aggregate), not something the Builder should hardcode.
    # The discovery trigger endpoint is disabled (503) until both the
    # board and the trigger token are configured.
    job_discovery_greenhouse_board_token: str | None = None
    job_discovery_greenhouse_company_name: str | None = None
    # Shared secret an external scheduler (cron, platform scheduled task)
    # presents to POST /internal/job-discovery/run. This is a system-to-
    # system credential, not a user permission - there is no admin/role
    # concept on User to hang this off of instead.
    job_discovery_trigger_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()