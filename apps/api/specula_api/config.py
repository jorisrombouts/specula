from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `.env` lives at the repo root, but the entrypoints run from `apps/api` (every `just` recipe
# cds there), so a CWD-relative ".env" resolves to a file that isn't there and the real keys
# load as "". Read the repo-root file by absolute path; a CWD-local `.env` still wins over it
# (the per-worktree `apps/api/.env` files the fan-out lanes use keep working).
_REPO_ROOT = Path(__file__).resolve().parents[3]

# An env var that is present-but-empty (`PIPELINE_MODE=` in a .env) means "not set", not
# an invalid value — without this, sourcing such a .env crashes every entrypoint that
# builds Settings (seed, CLI, uvicorn) with a Literal validation error.
_BLANK_DEFAULTS = {"pipeline_mode": "live", "pipeline_execution": "inline"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(_REPO_ROOT / ".env", ".env"), extra="ignore")

    @field_validator("pipeline_mode", "pipeline_execution", mode="before")
    @classmethod
    def _blank_means_default(cls, value: Any, info: ValidationInfo) -> Any:
        if isinstance(value, str) and not value.strip() and info.field_name is not None:
            return _BLANK_DEFAULTS[info.field_name]
        return value

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
    # Dedup (spec §5): two postings at the same company are the same role when their titles
    # match on trigram AND their title_vec cosine clears the threshold. Both must hold — the
    # vector alone conflates sibling roles ("Senior" vs "Staff"), and trigram alone conflates
    # unrelated roles that share wording ("Engineering Manager" vs "Engineer").
    dedup_title_similarity: float = 0.45
    dedup_vector_similarity: float = 0.92
    pipeline_mode: Literal["live", "recorded", "record"] = "live"
    pipeline_execution: Literal["enqueue", "inline"] = "inline"  # no Redis/worker this milestone
    pipeline_fixtures_dir: str | None = None


settings = Settings()
