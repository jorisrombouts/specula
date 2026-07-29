from specula_api.config import Settings, settings


def test_discovery_defaults() -> None:
    s = Settings()
    assert s.discovery_max_searches == 10
    # gpt-4o (not mini): mini rejects the web_search allowed_domains filter discovery needs.
    assert s.openai_discovery_model == "gpt-4o"


def test_m5_settings_present() -> None:
    assert settings.run_rate_limit_per_hour > 0
    assert settings.run_cooldown_s >= 0
    assert settings.log_level == "INFO"
    assert settings.sentry_dsn is None
    assert settings.otel_enabled is False
