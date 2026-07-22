"""Read-model aggregates over the user's LLM spend + runs. Everything here is DERIVED at
read time — nothing is a stored count. Every query is scoped by `user_id` (belt-and-
suspenders alongside RLS). Total spend sums `llm_costs` (not `runs.cost_usd`): company
ingest — the dominant spend — creates no Run, so only the ledger holds the full picture.
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import LlmCost, Run
from specula_api.schemas.dashboard import CostByStage, CostPoint, DashboardSummary
from specula_api.schemas.run import RunOut

# How many of the most recent runs the dashboard surfaces.
RECENT_RUN_LIMIT = 10


def _utc_date(dt: datetime) -> date:
    """Day the row belongs to, in UTC — independent of the DB session's timezone."""
    return dt.astimezone(UTC).date()


async def compute_dashboard(session: AsyncSession, user_id: UUID) -> DashboardSummary:
    costs = (await session.scalars(select(LlmCost).where(LlmCost.user_id == user_id))).all()
    runs = (
        await session.scalars(
            select(Run).where(Run.user_id == user_id).order_by(Run.created_at.desc())
        )
    ).all()

    total = sum((c.cost_usd for c in costs), Decimal(0))

    stage_totals: dict[str, Decimal] = defaultdict(Decimal)
    cost_by_day: dict[date, Decimal] = defaultdict(Decimal)
    for c in costs:
        stage_totals[c.stage] += c.cost_usd
        cost_by_day[_utc_date(c.created_at)] += c.cost_usd

    runs_by_day: dict[date, int] = defaultdict(int)
    for r in runs:
        runs_by_day[_utc_date(r.created_at)] += 1

    cost_by_stage = sorted(
        (
            CostByStage(stage=stage, cost_usd=float(amount))
            for stage, amount in stage_totals.items()
        ),
        key=lambda s: (-s.cost_usd, s.stage),
    )
    cost_by_day_points = [
        CostPoint(
            date=day.isoformat(),
            cost_usd=float(cost_by_day.get(day, Decimal(0))),
            runs=runs_by_day.get(day, 0),
        )
        for day in sorted(cost_by_day.keys() | runs_by_day.keys())
    ]

    return DashboardSummary(
        total_cost_usd=float(total),
        run_count=len(runs),
        cost_by_stage=cost_by_stage,
        cost_by_day=cost_by_day_points,
        recent_runs=[RunOut.from_model(r) for r in runs[:RECENT_RUN_LIMIT]],
    )
