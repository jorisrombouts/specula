from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://specula_app:specula@localhost:55432/specula"
    service_jwt_secret: str = ""
    service_jwt_issuer: str = "specula-web"
    service_jwt_audience: str = "specula-api"

    openai_api_key: str = ""
    openai_search_model: str = "gpt-4o"
    openai_extract_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    openai_rationale_model: str = "gpt-4o-mini"
    scoring_version: str = "v1"
    crawl_user_agent: str = "SpeculaBot/1.0 (+https://specula.app/bot)"
    crawl_per_domain_delay_ms: int = 1000
    crawl_timeout_s: float = 15.0
    discovery_max_searches: int = 5
    # Cap the per-company LLM extraction/scoring: a big board (Greenhouse can return 600+
    # jobs) would otherwise fire one extraction call per posting. Shells are still all
    # crawled (cheap); only this many are LLM-extracted + scored per ingest.
    ingest_max_postings: int = 25
    low_confidence_threshold: int = 50  # matches services/insights.py LOW_CONFIDENCE_THRESHOLD
    pipeline_mode: Literal["live", "recorded", "record"] = "live"
    pipeline_execution: Literal["enqueue", "inline"] = "inline"  # no Redis/worker this milestone
    pipeline_fixtures_dir: str | None = None


settings = Settings()
