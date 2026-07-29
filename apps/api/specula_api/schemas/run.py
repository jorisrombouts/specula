from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from specula_api.db.models import Run


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunStats(CamelModel):
    found: int = 0
    new: int = 0
    closed: int = 0
    low_conf_excluded: int = 0
    errors: int = 0
    scored: int = 0  # postings re-scored — only set by a rescore run


class RunTokens(CamelModel):
    total_tokens: int
    duration_ms: int | None = None


class RunOut(CamelModel):
    id: UUID
    kind: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats: RunStats
    created_at: datetime
    tokens: RunTokens | None = None

    @classmethod
    def from_model(cls, run: Run, total_tokens: int | None = None) -> "RunOut":
        """`total_tokens` is DERIVED from the `llm_costs` ledger by the caller (the dashboard
        service) — runs store no usage rollup. Callers that don't need it omit it, and
        `tokens` stays None."""
        tokens = (
            RunTokens(total_tokens=total_tokens, duration_ms=run.duration_ms)
            if total_tokens is not None
            else None
        )
        return cls(
            id=run.id,
            kind=run.kind,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            stats=RunStats.model_validate(run.stats),
            created_at=run.created_at,
            tokens=tokens,
        )
