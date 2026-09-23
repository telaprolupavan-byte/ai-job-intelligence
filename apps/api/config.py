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
    # "gpt-5.6" (with no suffix) is the bare model alias, which OpenAI
    # routes to GPT-5.6 Sol - the flagship frontier-reasoning tier. Sol
    # runs an explicit reasoning pass by default, which is appropriate
    # for frontier research/agentic-coding workloads but adds latency
    # that routinely exceeds this app's interactive, client-timeout-
    # bounded AI endpoints (resume/job/gap/requirement analysis all read
    # this same setting). Terra is OpenAI's recommended tier for this
    # kind of bounded-latency structured-extraction task.
    ai_model: str = "gpt-5.6-terra"
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
    # AJI-024: which discovery provider to run. Unset keeps the original
    # behavior (Greenhouse when its board settings are present). The only
    # other accepted value is "test_fixture", the deterministic offline
    # provider in services/job_discovery/sources/test_fixture.py - and it
    # additionally requires job_discovery_enable_test_provider=true, so a
    # single mistyped setting can never put synthetic jobs in front of
    # users. While the flag is false, fixture jobs are also hidden from
    # every user-facing job query.
    job_discovery_provider: str | None = None
    job_discovery_enable_test_provider: bool = False

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()