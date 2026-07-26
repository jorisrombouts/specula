from specula_api.config import OPENAI_PRICING, Settings, settings


def test_discovery_defaults() -> None:
    s = Settings()
    assert s.discovery_max_searches == 10
    # gpt-4o (not mini): mini rejects the web_search allowed_domains filter discovery needs.
    assert s.openai_discovery_model == "gpt-4o"
    assert s.openai_discovery_model in OPENAI_PRICING  # priced for the cost ledger


def test_m5_settings_present() -> None:
    assert settings.openai_run_budget_usd > 0
    assert settings.openai_daily_budget_usd >= settings.openai_run_budget_usd
    assert settings.run_rate_limit_per_hour > 0
    assert settings.run_cooldown_s >= 0
    assert settings.log_level == "INFO"
    assert settings.sentry_dsn is None
    assert settings.otel_enabled is False


def test_pricing_covers_configured_models() -> None:
    for m in (
        settings.openai_search_model,
        settings.openai_discovery_model,
        settings.openai_extract_model,
        settings.openai_embed_model,
        settings.openai_rationale_model,
    ):
        assert m in OPENAI_PRICING
        assert {"prompt", "completion", "embed"} <= set(OPENAI_PRICING[m])
