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
    # Skill overlap (spec §6.2): a required skill counts as covered when its embedding's
    # cosine to ANY candidate skill clears this. Exact/aliased skills share one canonical
    # cache entry, so they compare at 1.0 and always clear it; this threshold only decides
    # the semantic tail ("Machine Learning" covered by "PyTorch"). Tuned against the live
    # pool — see docs/SKILL-MATCHING.md.
    skill_match_similarity: float = 0.55
    # Must-have coverage (spec §6.2 red_flag). Same comparison as `skill_match_similarity`
    # but a stricter question — "is THIS skill present" rather than "is this requirement
    # covered" — so it gets its own threshold. Sits in the measured gap between the highest
    # false positive ("sql" covers "python" at 0.477, as does "gpu programming") and the
    # lowest true match ("python engineering", 0.617). Nothing in the live corpus falls
    # between: 0.50-0.60 all give zero false clears and zero wrong flags.
    must_have_similarity: float = 0.55
    pipeline_mode: Literal["live", "recorded", "record"] = "live"
    pipeline_execution: Literal["enqueue", "inline"] = "inline"  # no Redis/worker this milestone
    pipeline_fixtures_dir: str | None = None

    # --- M5 hardening ---
    openai_run_budget_usd: float = 5.0  # abort/mark a run/ingest if its LLM spend exceeds this
    openai_daily_budget_usd: float = 20.0  # per-user daily ceiling across runs
    run_rate_limit_per_hour: int = 10  # on-demand trigger cap (NET gate)
    run_cooldown_s: int = 60  # min seconds between a user's triggers
    log_level: str = "INFO"
    sentry_dsn: str | None = None  # None → Sentry disabled (live wiring deferred with hosting)
    otel_enabled: bool = False


# USD per 1,000,000 tokens. Embedding models bill only on `embed`.
# Verify rates against current OpenAI pricing before going live.
OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"prompt": 2.50, "completion": 10.00, "embed": 0.0},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60, "embed": 0.0},
    "text-embedding-3-small": {"prompt": 0.0, "completion": 0.0, "embed": 0.02},
}

settings = Settings()
