"""Read-model aggregates over the user's LLM token usage + runs. Everything here is DERIVED
at read time — nothing is a stored count. Every query is scoped by `user_id` (belt-and-
suspenders alongside RLS). Totals sum `llm_costs` rather than any per-run rollup: company
ingest — the dominant usage — creates no Run, so only the ledger holds the full picture.
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import LlmCost, Run
from specula_api.schemas.dashboard import DashboardSummary, TokenPoint, TokensByStage
from specula_api.schemas.run import RunOut

# How many of the most recent runs the dashboard surfaces.
RECENT_RUN_LIMIT = 10


def _utc_date(dt: datetime) -> date:
    """Day the row belongs to, in UTC — independent of the DB session's timezone."""
    return dt.astimezone(UTC).date()


def _row_tokens(c: LlmCost) -> int:
    """One ledger row's total token count. Prompt/completion/embed price differently, but the
    dashboard's headline is a single volume figure — the per-stage split carries the nuance."""
    return c.prompt_tokens + c.completion_tokens + c.embed_tokens


async def compute_dashboard(session: AsyncSession, user_id: UUID) -> DashboardSummary:
    costs = (await session.scalars(select(LlmCost).where(LlmCost.user_id == user_id))).all()
    runs = (
        await session.scalars(
            select(Run).where(Run.user_id == user_id).order_by(Run.created_at.desc())
        )
    ).all()

    total = sum(_row_tokens(c) for c in costs)

    stage_totals: dict[str, int] = defaultdict(int)
    tokens_by_day: dict[date, int] = defaultdict(int)
    tokens_by_run: dict[UUID, int] = {}
    for c in costs:
        stage_totals[c.stage] += _row_tokens(c)
        tokens_by_day[_utc_date(c.created_at)] += _row_tokens(c)
        if c.run_id is not None:
            tokens_by_run[c.run_id] = tokens_by_run.get(c.run_id, 0) + _row_tokens(c)

    runs_by_day: dict[date, int] = defaultdict(int)
    for r in runs:
        runs_by_day[_utc_date(r.created_at)] += 1

    tokens_by_stage = sorted(
        (TokensByStage(stage=stage, total_tokens=amount) for stage, amount in stage_totals.items()),
        key=lambda s: (-s.total_tokens, s.stage),
    )
    tokens_by_day_points = [
        TokenPoint(
            date=day.isoformat(),
            total_tokens=tokens_by_day.get(day, 0),
            runs=runs_by_day.get(day, 0),
        )
        for day in sorted(tokens_by_day.keys() | runs_by_day.keys())
    ]

    return DashboardSummary(
        total_tokens=total,
        run_count=len(runs),
        tokens_by_stage=tokens_by_stage,
        tokens_by_day=tokens_by_day_points,
        recent_runs=[
            # `.get` with NO default: a run with no ledger rows passes None, so `tokens`
            # serializes as null. "Nothing recorded" must stay distinct from "recorded zero".
            RunOut.from_model(r, total_tokens=tokens_by_run.get(r.id))
            for r in runs[:RECENT_RUN_LIMIT]
        ],
    )
