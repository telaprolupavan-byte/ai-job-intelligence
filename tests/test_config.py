from apps.api.config import Settings


def test_default_ai_model_avoids_the_frontier_reasoning_alias(monkeypatch):
    """Regression test for the resume/job/gap/requirement AI-analysis
    timeout: the bare "gpt-5.6" model string is a family alias that
    OpenAI routes to GPT-5.6 Sol, the flagship frontier-reasoning tier.
    Sol's default reasoning pass can push a structured-extraction
    request past this app's bounded AI request timeout, surfacing as
    "OpenAI request timed out" even though the request eventually would
    have succeeded. `ai_model` must default to a specific, bounded-
    latency tier instead of the alias.
    """
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    settings = Settings(_env_file=None)

    assert settings.ai_model == "gpt-5.6-terra"
    assert settings.ai_model != "gpt-5.6"
