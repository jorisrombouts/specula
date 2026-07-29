# Tokens, Not Cost — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop deriving, storing, and displaying USD cost anywhere in Specula — the LLM ledger records token counts only — and remove the USD budget guard entirely.

**Architecture:** `llm_costs` already stores `prompt_tokens`/`completion_tokens`/`embed_tokens` per metered call; `cost_usd` was a *derived* column computed from a hard-coded price table. We delete the price table, the derivation, and both stored rollups (`llm_costs.cost_usd`, `runs.cost_usd`). Read models (dashboard, GDPR export, `RunOut`) switch to summing tokens. Per-run token totals are **derived** from the ledger at read time rather than stored, honoring the project invariant "counts are DERIVED server-side, never stored."

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 · Alembic · Pydantic v2 · pytest · Next.js 16 · TypeScript strict · Vitest · Playwright

## Global Constraints

- **No budget guard exists after this change.** `BudgetExceeded`, `CostSink`'s ceilings, the daily-baseline seeding, and `openai_run_budget_usd` / `openai_daily_budget_usd` are all removed. Nothing replaces them. This was an explicit product decision (2026-07-29); do not reintroduce a spend cap.
- **The migration is destructive and irreversible.** Dropping `cost_usd` discards all historical spend. Downgrade recreates the columns as NULL/0 — the original values are unrecoverable. This was explicitly accepted.
- **Table/model/contract names that say "cost" are KEPT**: the `llm_costs` table, the `LlmCost` SQLAlchemy model, and the frozen `llmCosts` GDPR export key. Renaming the table adds migration risk for zero functional gain, and `llmCosts` is a frozen GDPR contract key. Only *internal Python* names whose "cost" is now a lie get renamed (`CostRecord`→`UsageRecord`, `CostSink`→`UsageSink`, `deps.cost_sink`→`deps.usage_sink`, `_persist_costs`→`_persist_usage`).
- **"Total tokens" means `prompt_tokens + completion_tokens + embed_tokens`.** One summed integer. Mixing the three is imprecise (they price differently) but this is the headline figure; per-stage and per-day breakdowns are preserved.
- `mypy --strict` and `ruff` must pass on `apps/api`; `tsc --noEmit`, ESLint, and Prettier must pass on `apps/web`.
- Run API tests with `cd apps/api && uv run pytest`; web tests with `cd apps/web && pnpm test`.

## File Structure

**API — modified:**
- `apps/api/specula_api/config.py` — drop `OPENAI_PRICING`, both `*_budget_usd` settings
- `apps/api/specula_api/pipeline/openai_client.py` — drop `compute_cost_usd`, `BudgetExceeded`; `CostSink`→`UsageSink` (pure accumulator), `CostRecord`→`UsageRecord`
- `apps/api/specula_api/pipeline/deps.py` — sink construction without budgets; field rename
- `apps/api/specula_api/services/run.py` — drop baseline seeding + budget handling; `_persist_costs`→`_persist_usage`
- `apps/api/specula_api/services/dashboard.py` — aggregate tokens
- `apps/api/specula_api/services/account.py` — export without cost
- `apps/api/specula_api/schemas/dashboard.py` — `TokensByStage`, `TokenPoint`, token summary
- `apps/api/specula_api/schemas/run.py` — `RunCost`→`RunTokens`
- `apps/api/specula_api/schemas/account.py` — `LlmCostExport` drops `cost_usd`
- `apps/api/specula_api/db/models/llm_cost.py` — drop `cost_usd`
- `apps/api/specula_api/db/models/run.py` — drop `cost_usd`
- `apps/api/specula_api/services/dashboard.py` — derive per-run token totals

**API — created:**
- `apps/api/alembic/versions/a1c4e7d90b23_drop_cost_usd.py`

**Shared/web — modified:**
- `packages/shared-types/src/index.ts` — contract change
- `apps/web/src/components/dashboard/dashboard-view.tsx` — render tokens
- `apps/web/src/components/dashboard/dashboard-view.test.tsx`
- `apps/web/e2e/authed/dashboard.spec.ts`

**Docs — modified:**
- `docs/M5-STATUS.md` — cost follow-ups are moot/changed

---

### Task 1: Remove the budget guard

Self-contained: after this task cost is still computed and stored, but nothing aborts on spend. Ends green.

**Files:**
- Modify: `apps/api/specula_api/config.py:82-83`
- Modify: `apps/api/specula_api/pipeline/openai_client.py:560-599`
- Modify: `apps/api/specula_api/pipeline/deps.py:73-79`
- Modify: `apps/api/specula_api/services/run.py:27-40,136,149-161,192,206-216,265,271-278,445,459-469`
- Test: `apps/api/tests/test_metering.py:135-161`, `apps/api/tests/test_run_cost.py:229-264,282-336`, `apps/api/tests/test_config_m5.py:12-21`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `CostSink(records: list[CostRecord])` — constructor takes **no arguments**; `.add(record)` never raises; `.total` retained. `BudgetExceeded` no longer exists.

- [ ] **Step 1: Delete the budget tests that assert removed behavior**

In `apps/api/tests/test_metering.py`, delete these four tests entirely:
`test_costsink_raises_when_run_budget_exceeded`, `test_costsink_daily_baseline_counts_toward_ceiling`, `test_costsink_raises_when_daily_budget_exceeded`, `test_budget_exceeded_is_not_a_plain_exception`.

In `apps/api/tests/test_run_cost.py`, delete `test_run_budget_exceeded_marks_error_and_stops_calls`, `test_budget_exceeded_survives_discovery_broad_except`, and `test_daily_budget_baseline_seeded_from_prior_spend`.

Remove now-unused imports (`BudgetExceeded`) from both files.

- [ ] **Step 2: Write the failing test that the sink no longer caps**

Add to `apps/api/tests/test_metering.py`:

```python
def test_usage_sink_never_caps_regardless_of_volume() -> None:
    """The budget guard was removed (2026-07-29). A sink accumulates without limit."""
    sink = CostSink()
    for _ in range(50):
        sink.add(
            CostRecord(
                stage="rationale",
                model="gpt-4o",
                prompt_tokens=1_000_000,
                completion_tokens=1_000_000,
                embed_tokens=0,
                cost_usd=Decimal("12.50"),
            )
        )
    assert len(sink.records) == 50
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_metering.py::test_usage_sink_never_caps_regardless_of_volume -v`
Expected: FAIL — `TypeError: CostSink.__init__() missing 2 required positional arguments: 'run_budget_usd' and 'daily_budget_usd'`

- [ ] **Step 4: Strip the guard from `CostSink` and delete `BudgetExceeded`**

In `apps/api/specula_api/pipeline/openai_client.py`, delete the entire `BudgetExceeded` class, and replace the `CostSink` dataclass with:

```python
@dataclass
class CostSink:
    """Accumulates a run/ingest's `CostRecord`s.

    In-memory only — services/run.py reads `records` afterward to write `llm_costs` rows.
    There is no spend ceiling: the USD budget guard was removed on 2026-07-29 (tokens are
    metered, cost is not). Nothing here aborts a run."""

    records: list[CostRecord] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((rec.cost_usd for rec in self.records), Decimal("0"))

    def add(self, record: CostRecord) -> None:
        self.records.append(record)
```

- [ ] **Step 5: Update `deps.py` sink construction**

In `apps/api/specula_api/pipeline/deps.py`, replace lines 73-79's body:

```python
def with_metering(deps: PipelineDeps, settings: Settings) -> PipelineDeps:
    """Wrap deps.openai in token metering feeding a fresh per-run CostSink (OBS)."""
    sink = CostSink()
    return replace(deps, openai=MeteringOpenAIClient(deps.openai, sink, settings), cost_sink=sink)
```

- [ ] **Step 6: Strip budget handling from `services/run.py`**

Delete the entire `_seed_daily_baseline` function (lines 27-40) and all four `await _seed_daily_baseline(...)` call sites (lines 136, 192, 265, 445).

Delete all four `except BudgetExceeded as exc:` blocks and their bodies — in `run_discovery` (lines 158-161), `run_rescore` (~213-216), `ingest_company` (271-277), and `run_refresh` (~466-469). In `ingest_company` the `try:` now has only the `finally:` clause, which is valid Python and still persists usage:

```python
        try:
            await _ingest_pipeline(session, user_id, company, deps)
            _log.info("ingest.done", extra={"company_id": str(company.id)})
        finally:
            await _persist_costs(session, user_id, deps, run_id=None, company_id=company.id)
```

Remove the `BudgetExceeded` import (line 20) and the now-unused `func` import if `_seed_daily_baseline` was its only user — verify with `grep -n "func\." specula_api/services/run.py` before removing.

Update `ingest_company`'s docstring: drop "and aborts cleanly on a budget breach — costs already accrued are still persisted (finally)", keep the persistence note. Update `run_rescore`'s and `run_refresh`'s docstrings to say "the same cost ledger + observability as discovery" (drop "budget guard +").

- [ ] **Step 7: Drop the budget settings from config**

In `apps/api/specula_api/config.py`, delete lines 82-83 (`openai_run_budget_usd`, `openai_daily_budget_usd`). Update `apps/api/tests/test_config_m5.py::test_m5_settings_present` to stop asserting them — remove any `openai_run_budget_usd` / `openai_daily_budget_usd` assertions from that test.

- [ ] **Step 8: Run the full API suite**

Run: `cd apps/api && uv run pytest -q`
Expected: PASS (count will be ~480, down from 487 — seven budget tests deleted, one added)

- [ ] **Step 9: Lint and type-check**

Run: `cd apps/api && uv run ruff check && uv run mypy .`
Expected: both clean

- [ ] **Step 10: Commit**

```bash
git add apps/api
git commit -m "refactor(cost): remove the USD budget guard

The per-run/per-day spend ceilings, BudgetExceeded, and the daily-baseline
seeding are gone. Metering still records tokens and cost; nothing aborts."
```

---

### Task 2: Switch read models and the web contract from cost to tokens

The `cost_usd` columns still exist and are still written — this task only stops *reading* them. API + shared-types + web move together because they are one contract. Ends green.

**Files:**
- Modify: `apps/api/specula_api/schemas/dashboard.py`
- Modify: `apps/api/specula_api/schemas/run.py:22-53`
- Modify: `apps/api/specula_api/services/dashboard.py`
- Modify: `apps/api/specula_api/schemas/account.py:124,129-141`
- Modify: `packages/shared-types/src/index.ts:115-130`
- Modify: `apps/web/src/components/dashboard/dashboard-view.tsx`
- Test: `apps/api/tests/test_dashboard_api.py`, `apps/api/tests/test_run_schema_cost.py`, `apps/web/src/components/dashboard/dashboard-view.test.tsx`, `apps/web/e2e/authed/dashboard.spec.ts`

**Interfaces:**
- Consumes: `CostSink` with no budget args (Task 1).
- Produces:
  - `TokensByStage(stage: str, total_tokens: int)`
  - `TokenPoint(date: str, total_tokens: int, runs: int)`
  - `DashboardSummary(total_tokens: int, run_count: int, tokens_by_stage: list[TokensByStage], tokens_by_day: list[TokenPoint], recent_runs: list[RunOut])`
  - `RunTokens(total_tokens: int, duration_ms: int | None)`
  - `RunOut.from_model(run: Run, total_tokens: int | None = None) -> RunOut` — `tokens` is populated only when a caller supplies a derived total.
  - TS: `TokensByStage`, `TokenPoint`, `RunTokens`, `DashboardSummary.totalTokens/tokensByStage/tokensByDay`, `Run.tokens`.

- [ ] **Step 1: Rework the dashboard test seeding helper, then the tests**

⚠️ **The existing `_seed` helper cannot express this task's data.** Two gaps must be closed first or every rewritten test passes vacuously:

1. Its cost dicts set only `cost_usd` — token columns fall back to `server_default="0"`, so token assertions would compare `0 == 0`.
2. It creates `llm_costs` rows with **no `run_id`**, and seeds `Run.cost_usd` directly. Per-run totals are now DERIVED from `llm_costs.run_id`, so a run's tokens can only be tested if cost rows can be attached to a run.

In `apps/api/tests/test_dashboard_api.py`, replace `_seed` with this version. It creates runs first, then attaches cost rows to a run by list index via a `run` key:

```python
async def _seed(
    *,
    sub: str,
    costs: list[dict[str, object]] | None = None,
    runs: list[dict[str, object]] | None = None,
) -> uuid.UUID:
    """Create a fresh user and the given llm_costs + runs rows, committed so the API
    (a separate session, matched by google_sub) can read them under RLS. Each cost dict
    may set stage/model/prompt_tokens/completion_tokens/embed_tokens/created_at, plus
    `run` — an index into `runs` linking the row to that run (omit for ingest-style rows
    that belong to no run). Each run dict may set kind/status/duration_ms/created_at."""
    async with async_session() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", google_sub=sub)
        session.add(user)
        await session.flush()
        await _set_tenant(session, user.id)

        run_models: list[Run] = []
        for spec in runs or []:
            run = Run(
                user_id=user.id,
                kind=str(spec.get("kind", "on_demand")),
                status=str(spec.get("status", "done")),
                duration_ms=spec.get("duration_ms"),
                created_at=spec.get("created_at", DAY_A),
            )
            session.add(run)
            run_models.append(run)
        await session.flush()  # assign run ids before linking cost rows

        for spec in costs or []:
            idx = spec.get("run")
            session.add(
                LlmCost(
                    user_id=user.id,
                    run_id=run_models[int(idx)].id if idx is not None else None,
                    stage=str(spec.get("stage", "extract")),
                    model=str(spec.get("model", "gpt-4o-mini")),
                    prompt_tokens=int(spec.get("prompt_tokens", 0)),
                    completion_tokens=int(spec.get("completion_tokens", 0)),
                    embed_tokens=int(spec.get("embed_tokens", 0)),
                    created_at=spec.get("created_at", DAY_A),
                )
            )
        await session.commit()
        return user.id
```

Move the `DAY_A`/`DAY_B` constants above `_seed` (it now references `DAY_A` as a default). Remove the `Decimal` import if nothing else in the file uses it.

Now rewrite the five tests. `test_dashboard_empty_for_fresh_user` and `test_cross_tenant_isolation` swap their four assertions to `body["totalTokens"] == 0`, `body["tokensByStage"] == []`, `body["tokensByDay"] == []` (the `runCount`/`recentRuns` assertions are unchanged); `test_cross_tenant_isolation`'s seed drops `cost_usd` for `{"stage": "score", "prompt_tokens": 500, "created_at": DAY_A}`.

Replace `test_dashboard_aggregates_costs_and_runs` with:

```python
@requires_db
async def test_dashboard_aggregates_tokens_and_runs(migrated_db: None) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        costs=[
            {"stage": "extract", "prompt_tokens": 800, "completion_tokens": 200,
             "created_at": DAY_A},
            {"stage": "embed", "embed_tokens": 100, "created_at": DAY_A},
            {"stage": "extract", "prompt_tokens": 400, "completion_tokens": 100,
             "created_at": DAY_B},
            {"stage": "score", "prompt_tokens": 1500, "completion_tokens": 500,
             "created_at": DAY_B},
        ],
        runs=[
            {"created_at": DAY_A},
            {"created_at": DAY_B},
            {"created_at": DAY_B},
        ],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]

    assert body["totalTokens"] == 3600  # 1000 + 100 + 500 + 2000
    assert body["runCount"] == 3
    assert "totalCostUsd" not in body

    # tokensByStage: summed per stage, ordered by volume desc.
    stages = body["tokensByStage"]
    assert [s["stage"] for s in stages] == ["score", "extract", "embed"]
    by_stage = {s["stage"]: s["totalTokens"] for s in stages}
    assert by_stage["extract"] == 1500
    assert by_stage["score"] == 2000
    assert by_stage["embed"] == 100

    # tokensByDay: one point per day (ascending), tokens from llm_costs, runs from runs.
    days = body["tokensByDay"]
    assert [p["date"] for p in days] == ["2026-07-05", "2026-07-06"]
    assert days[0]["totalTokens"] == 1100
    assert days[0]["runs"] == 1
    assert days[1]["totalTokens"] == 2500
    assert days[1]["runs"] == 2
```

Replace `test_cost_day_includes_days_with_costs_but_no_run` with:

```python
@requires_db
async def test_token_day_includes_days_with_usage_but_no_run(migrated_db: None) -> None:
    # Company ingest spends LLM tokens without creating a Run (see LlmCost docstring):
    # such a day must still appear, with runs == 0.
    sub = _sub()
    await _seed(
        sub=sub,
        costs=[{"stage": "extract", "prompt_tokens": 300, "created_at": DAY_A}],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]
    assert body["runCount"] == 0
    assert body["tokensByDay"] == [{"date": "2026-07-05", "totalTokens": 300, "runs": 0}]
```

Replace `test_recent_runs_carry_cost_and_are_newest_first` with a version that links ledger rows to a run:

```python
@requires_db
async def test_recent_runs_carry_derived_tokens_and_are_newest_first(
    migrated_db: None,
) -> None:
    sub = _sub()
    await _seed(
        sub=sub,
        runs=[
            {"kind": "scheduled", "status": "done", "created_at": DAY_A},
            {"kind": "on_demand", "status": "error", "duration_ms": 1234,
             "created_at": DAY_B},
        ],
        # Both rows belong to run index 1 — its total is DERIVED as their sum.
        costs=[
            {"stage": "discovery", "prompt_tokens": 700, "run": 1, "created_at": DAY_B},
            {"stage": "score", "completion_tokens": 300, "run": 1, "created_at": DAY_B},
        ],
    )

    body = (await _get("/api/v1/dashboard", sub)).json()  # type: ignore[attr-defined]
    recent = body["recentRuns"]
    assert len(recent) == 2
    # Newest first.
    assert recent[0]["kind"] == "on_demand"
    assert recent[0]["status"] == "error"
    assert recent[0]["tokens"]["totalTokens"] == 1000
    assert recent[0]["tokens"]["durationMs"] == 1234
    # A run with NO ledger rows serializes tokens as null — "nothing recorded" is
    # distinct from "recorded zero".
    assert recent[1]["kind"] == "scheduled"
    assert recent[1]["tokens"] is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_dashboard_api.py -v`
Expected: FAIL — `KeyError: 'totalTokens'`

- [ ] **Step 3: Rewrite the dashboard schemas**

Replace the schema classes in `apps/api/specula_api/schemas/dashboard.py`:

```python
class TokensByStage(CamelModel):
    stage: str
    total_tokens: int


class TokenPoint(CamelModel):
    date: str  # YYYY-MM-DD (frozen contract types this as a string)
    total_tokens: int
    runs: int


class DashboardSummary(CamelModel):
    total_tokens: int
    run_count: int
    tokens_by_stage: list[TokensByStage]
    tokens_by_day: list[TokenPoint]
    recent_runs: list[RunOut]
```

- [ ] **Step 4: Rewrite the dashboard service**

Replace the body of `apps/api/specula_api/services/dashboard.py` below the imports. Update the module docstring's first paragraph to say token usage rather than spend, and note that per-run totals are derived from the ledger:

```python
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
    tokens_by_run: dict[UUID, int] = defaultdict(int)
    for c in costs:
        stage_totals[c.stage] += _row_tokens(c)
        tokens_by_day[_utc_date(c.created_at)] += _row_tokens(c)
        if c.run_id is not None:
            tokens_by_run[c.run_id] += _row_tokens(c)

    runs_by_day: dict[date, int] = defaultdict(int)
    for r in runs:
        runs_by_day[_utc_date(r.created_at)] += 1

    tokens_by_stage = sorted(
        (
            TokensByStage(stage=stage, total_tokens=amount)
            for stage, amount in stage_totals.items()
        ),
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
```

Note `tokens_by_run` is a plain `dict[UUID, int]` here, NOT a `defaultdict` — a defaultdict's `.get()` still returns None for missing keys, but using a plain dict makes the intent unmistakable. Build it as `tokens_by_run: dict[UUID, int] = {}` and accumulate with `tokens_by_run[c.run_id] = tokens_by_run.get(c.run_id, 0) + _row_tokens(c)`.

- [ ] **Step 5: Switch `RunOut` to derived tokens**

In `apps/api/specula_api/schemas/run.py`, replace `RunCost` and `RunOut.from_model`:

```python
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
```

Update `apps/api/tests/test_run_schema_cost.py::test_runout_serialises_cost_camel` — rename the file to `test_run_schema_tokens.py` and the test to `test_runout_serialises_tokens_camel`, asserting `RunOut.from_model(run, total_tokens=1234).model_dump(by_alias=True)["tokens"]["totalTokens"] == 1234`.

- [ ] **Step 6: Drop cost from the GDPR export schema**

In `apps/api/specula_api/schemas/account.py`, delete `cost_usd: float | None` (line 124, the `RunExport` field) and `cost_usd: float` (line 140, in `LlmCostExport`). Update the `LlmCostExport` docstring to `"""Serializes to the frozen `LlmCost` interface — token counts only."""` and the module docstring's line 5 to drop "(cost as a JSON number, not a ...)".

`apps/api/specula_api/services/account.py` needs no change — it uses `model_validate`.

- [ ] **Step 7: Run API tests**

Run: `cd apps/api && uv run pytest -q && uv run ruff check && uv run mypy .`
Expected: PASS, clean

- [ ] **Step 8: Update the shared-types contract**

In `packages/shared-types/src/index.ts`, replace lines 115-130:

```ts
  stats: RunStats; createdAt: string; tokens?: RunTokens | null;
}

export interface LlmCost {
  id: string; runId: string | null; companyId: string | null;
  stage: string; model: string;
  promptTokens: number; completionTokens: number; embedTokens: number;
  createdAt: string;
}
export interface RunTokens { totalTokens: number; durationMs: number | null }
export interface TokenPoint { date: string; totalTokens: number; runs: number }
export interface TokensByStage { stage: string; totalTokens: number }
export interface DashboardSummary {
  totalTokens: number; runCount: number;
  tokensByStage: TokensByStage[]; tokensByDay: TokenPoint[]; recentRuns: Run[];
}
```

Also remove `costUsd` from `RunExport`'s TS counterpart if one exists — `grep -n "costUsd" packages/shared-types/src/index.ts` must return nothing when done.

- [ ] **Step 9: Update the web dashboard view**

In `apps/web/src/components/dashboard/dashboard-view.tsx`: delete the `usd` helper (lines 3-5) and add a token formatter:

```ts
function tokens(n: number): string {
  return n.toLocaleString("en-US");
}
```

Then repoint every reading. Lines 60-61 become:

```ts
  const stageMax = Math.max(1, ...s.tokensByStage.map((x) => x.totalTokens));
  const dayMax = Math.max(1, ...s.tokensByDay.map((x) => x.totalTokens));
```

Line 74's copy: `Internal run & usage observability — LLM tokens per stage, per` (keep the rest of the sentence structure intact). Line 81: `<Tile label="Total LLM tokens" value={tokens(s.totalTokens)} />`. Lines 87-99 and 108-122: swap `s.costByStage`→`s.tokensByStage`, `s.costByDay`→`s.tokensByDay`, `row.costUsd`→`row.totalTokens`, `usd(row.costUsd, 4)`→`tokens(row.totalTokens)`. Line 143: `<span className="text-right">Tokens</span>`. Line 171: `{run.tokens ? tokens(run.tokens.totalTokens) : "—"}`.

`1e-9` becomes `1` in the max guards because token counts are integers — a zero-token dashboard divides by 1, not a float epsilon.

- [ ] **Step 10: Update web tests**

In `apps/web/src/components/dashboard/dashboard-view.test.tsx`, replace the fixture's cost fields with token fields and assert on a formatted token count (e.g. `expect(screen.getByText("1,234")).toBeInTheDocument()`) instead of a `$` string. In `apps/web/e2e/authed/dashboard.spec.ts`, repoint the two cost assertions at the "Total LLM tokens" tile.

- [ ] **Step 11: Run web tests**

Run: `cd apps/web && pnpm test && pnpm typecheck && pnpm lint`
Expected: all PASS/clean

- [ ] **Step 12: Commit**

```bash
git add apps/api packages/shared-types apps/web
git commit -m "refactor(dashboard): report LLM tokens instead of USD spend

Dashboard, RunOut and the GDPR export now read token counts. Per-run totals
are derived from the llm_costs ledger rather than a stored rollup, per the
'counts are derived' invariant. cost_usd columns still exist but are unread."
```

---

### Task 3: Drop the cost columns, the price table, and the cost derivation

Nothing reads `cost_usd` after Task 2, so it can now be removed end-to-end. Ends green.

**Files:**
- Modify: `apps/api/specula_api/pipeline/openai_client.py`
- Modify: `apps/api/specula_api/config.py:96-101`
- Modify: `apps/api/specula_api/services/run.py`
- Modify: `apps/api/specula_api/pipeline/deps.py`
- Modify: `apps/api/specula_api/db/models/llm_cost.py:29`
- Modify: `apps/api/specula_api/db/models/run.py:25`
- Create: `apps/api/alembic/versions/a1c4e7d90b23_drop_cost_usd.py`
- Modify: `docs/M5-STATUS.md`
- Test: `apps/api/tests/test_llm_cost_model.py`, `apps/api/tests/test_metering.py`, `apps/api/tests/test_run_cost.py`, `apps/api/tests/test_config_m5.py`, `apps/api/tests/test_deps_metering.py`

**Interfaces:**
- Consumes: token-based read models (Task 2).
- Produces: `UsageRecord(stage, model, prompt_tokens, completion_tokens, embed_tokens)` — no `cost_usd`. `UsageSink(records: list[UsageRecord])` with `.add()`, no `.total`. `PipelineDeps.usage_sink: UsageSink | None`.

- [ ] **Step 1: Write the failing model test**

In `apps/api/tests/test_llm_cost_model.py`, update `test_llm_cost_table_and_columns` to assert absence:

```python
def test_llm_cost_table_and_columns() -> None:
    cols = set(LlmCost.__table__.columns.keys())
    assert {"prompt_tokens", "completion_tokens", "embed_tokens"} <= cols
    assert "cost_usd" not in cols, "cost is no longer tracked (2026-07-29)"


def test_run_has_no_cost_rollup() -> None:
    assert "cost_usd" not in set(Run.__table__.columns.keys())
```

Import `Run` in that file if not already imported. Update `test_company_optout_and_run_rollups_exist` to stop asserting `runs.cost_usd` — keep its `duration_ms` and `companies.opt_out` assertions.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_llm_cost_model.py -v`
Expected: FAIL — `AssertionError: cost is no longer tracked (2026-07-29)`

- [ ] **Step 3: Drop the columns from the models**

In `apps/api/specula_api/db/models/llm_cost.py`, delete line 29 (`cost_usd`) and the now-unused `Decimal` / `Numeric` imports if nothing else uses them.

In `apps/api/specula_api/db/models/run.py`, delete line 25 (`cost_usd`) and its now-unused `Decimal` / `Numeric` imports if unused.

- [ ] **Step 4: Write the migration**

Create `apps/api/alembic/versions/a1c4e7d90b23_drop_cost_usd.py`:

```python
"""drop cost_usd — Specula meters tokens, not cost

Destructive and irreversible: historical spend is discarded. The downgrade recreates the
columns with their original defaults, but the original values are unrecoverable. Accepted
deliberately on 2026-07-29 alongside the removal of the USD budget guard.

Revision ID: a1c4e7d90b23
Revises: d3f7a1c9e2b4
"""

import sqlalchemy as sa
from alembic import op

revision = "a1c4e7d90b23"
down_revision = "d3f7a1c9e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("llm_costs", "cost_usd")
    op.drop_column("runs", "cost_usd")


def downgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "llm_costs",
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
    )
```

Match the `revision`/`down_revision` type annotations to the style used by `d3f7a1c9e2b4_cheaper_discovery.py` — read that file first and mirror it (some revisions annotate as `str | None`).

- [ ] **Step 5: Apply the migration**

Run: `just up && cd apps/api && uv run alembic upgrade head`
Expected: applies `a1c4e7d90b23` with no error

Then verify the round-trip: `uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: both succeed

- [ ] **Step 6: Strip cost from the metering layer**

In `apps/api/specula_api/pipeline/openai_client.py`:

Delete `compute_cost_usd` entirely (lines 534-545) and the `OPENAI_PRICING` import.

Rename and shrink the record + sink:

```python
@dataclass(frozen=True)
class UsageRecord:
    """One metered OpenAI call. `stage` ∈ {discovery, extract, embed, score, rationale}.
    Tokens only — Specula does not price calls (2026-07-29)."""

    stage: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    embed_tokens: int


@dataclass
class UsageSink:
    """Accumulates a run/ingest's `UsageRecord`s.

    In-memory only — services/run.py reads `records` afterward to write `llm_costs` rows.
    There is no spend ceiling: the USD budget guard was removed on 2026-07-29."""

    records: list[UsageRecord] = field(default_factory=list)

    def add(self, record: UsageRecord) -> None:
        self.records.append(record)
```

In `MeteringOpenAIClient._record`, drop the `cost_usd=compute_cost_usd(...)` argument from the `UsageRecord(...)` construction and rename the constructed type. Update the section banner comment (lines 511-514) to say "Token metering — wraps any OpenAIClient, sizes each call and reports its token usage to a sink."

Update the `test_usage_sink_never_caps_regardless_of_volume` test from Task 1 to construct `UsageRecord`/`UsageSink` without `cost_usd`, and rename `test_each_call_records_one_row_with_stage_model_and_pricing_cost` → `test_each_call_records_one_row_with_stage_model_and_tokens`, dropping its cost assertion. Rename `test_embed_row_bills_only_embed_tokens` → `test_embed_row_records_only_embed_tokens`. Delete `test_costsink_total_sums_records` (there is no `.total`).

- [ ] **Step 7: Delete the price table**

In `apps/api/specula_api/config.py`, delete the `OPENAI_PRICING` dict and its two-line comment (lines 96-101).

Delete `apps/api/tests/test_config_m5.py::test_pricing_covers_configured_models` — it guarded a table that no longer exists. Remove the `OPENAI_PRICING` import from that file.

- [ ] **Step 8: Update `deps.py`**

Rename the field and construction in `apps/api/specula_api/pipeline/deps.py`:

```python
    usage_sink: UsageSink | None = None
```

```python
def with_metering(deps: PipelineDeps, settings: Settings) -> PipelineDeps:
    """Wrap deps.openai in token metering feeding a fresh per-run UsageSink (OBS)."""
    sink = UsageSink()
    return replace(deps, openai=MeteringOpenAIClient(deps.openai, sink, settings), usage_sink=sink)
```

Update the imports (`CostSink`→`UsageSink`). In `apps/api/tests/test_deps_metering.py`, rename `test_hand_built_deps_default_to_no_cost_sink` → `test_hand_built_deps_default_to_no_usage_sink` and repoint both tests at `usage_sink`.

- [ ] **Step 9: Update `services/run.py`**

Rename `_persist_costs` → `_persist_usage` and drop its return value (no caller uses it now that `run.cost_usd` is gone):

```python
async def _persist_usage(
    session: AsyncSession,
    user_id: UUID,
    deps: PipelineDeps,
    *,
    run_id: UUID | None,
    company_id: UUID | None,
) -> None:
    """Drain the usage sink into `llm_costs` rows (one per metered call). Company ingest
    creates no Run, so its rows carry `run_id=None, company_id=<id>` (OBS→DASH contract).
    Draining makes this safe to call once per run/ingest without double-counting."""
    sink = deps.usage_sink
    if sink is None:
        return
    created_at = deps.now()
    for record in sink.records:
        session.add(
            LlmCost(
                user_id=user_id,
                run_id=run_id,
                company_id=company_id,
                stage=record.stage,
                model=record.model,
                prompt_tokens=record.prompt_tokens,
                completion_tokens=record.completion_tokens,
                embed_tokens=record.embed_tokens,
                created_at=created_at,
            )
        )
    sink.records.clear()
    await session.flush()
```

Replace all four `run.cost_usd = await _persist_costs(...)` assignments with bare calls:

```python
            await _persist_usage(session, user_id, deps, run_id=run_id, company_id=None)
```

and the `ingest_company` `finally:` call with `await _persist_usage(session, user_id, deps, run_id=None, company_id=company.id)`.

Remove the now-unused `Decimal` import if nothing else in the file uses it. Update `run_refresh`'s docstring — delete "so this run's `cost_usd` rollup is 0 by design" (there is no rollup).

- [ ] **Step 10: Update the remaining cost tests**

In `apps/api/tests/test_run_cost.py`: rename `test_ingest_writes_llm_cost_rows_with_stage_model_and_pricing_cost` → `test_ingest_writes_llm_cost_rows_with_stage_model_and_tokens`, dropping cost assertions and keeping token/stage/model ones. Rename `test_discovery_run_records_cost_rollup_and_duration` → `test_discovery_run_records_usage_rows_and_duration`, asserting `llm_costs` rows exist for the run and `run.duration_ms is not None` instead of a `cost_usd` rollup. Keep `test_llm_costs_are_tenant_isolated` and `test_ingest_skips_opted_out_company` as-is apart from any `cost_usd` references.

In `apps/api/tests/test_openai_client_real_usage.py` and `apps/api/tests/test_m5_migration.py`, remove any `cost_usd` references — `grep -rn "cost_usd" tests/` must return nothing when done.

- [ ] **Step 11: Full verification**

Run: `cd apps/api && uv run pytest -q && uv run ruff check && uv run mypy .`
Expected: PASS, clean

Run: `cd apps/web && pnpm test && pnpm typecheck && pnpm lint`
Expected: PASS, clean

Run: `grep -rn "cost_usd\|costUsd\|OPENAI_PRICING\|BudgetExceeded\|compute_cost_usd\|budget_usd" apps packages --include="*.py" --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v "/.venv/" | grep -v alembic/versions`
Expected: no output (the alembic revisions legitimately retain the name)

- [ ] **Step 12: Update the status doc**

In `docs/M5-STATUS.md`, replace the four "Cost accounting (OBS)" bullets under "Follow-ups (M6 / backlog)" with a single note:

```markdown
**Cost accounting (OBS):** *Resolved 2026-07-29 — Specula no longer tracks cost.* The
`cost_usd` columns, the `OPENAI_PRICING` table, `compute_cost_usd`, and the USD budget
guard were all removed; `llm_costs` records token counts only and the dashboard reports
tokens. The unknown-model-bills-$0 bug, the budget-abort signal gap, and the stage
attribution note are moot. **There is no spend ceiling of any kind** — the OpenAI
account-level limit is now the only backstop.
- Stage attribution (unchanged): `enrich` is metered as stage `extract`; no `score` row.
- `rationale()`'s `chat.completions.create` usage-capture path is still untested.
- **Concurrency caveat** (unchanged): the `last_usage` side-channel is safe only because
  pipeline calls are strictly sequential today.
```

Also update the DASH row in the "What shipped" table: "Read-only run & **token** dashboard (tokens per stage/day/run + run status)".

- [ ] **Step 13: Commit**

```bash
git add apps packages docs
git commit -m "refactor(cost): drop cost_usd, the price table, and cost derivation

Specula meters tokens only. Removes llm_costs.cost_usd, runs.cost_usd,
OPENAI_PRICING and compute_cost_usd; CostRecord/CostSink become
UsageRecord/UsageSink. Migration is destructive: spend history is discarded.

Fixes the unknown-model-bills-\$0 bug by removing billing entirely."
```

---

## Self-Review

**Spec coverage:**
- Drop `llm_costs.cost_usd` → Task 3 Steps 3-5 ✓
- Drop `runs.cost_usd` → Task 3 Steps 3-5 ✓
- Drop `OPENAI_PRICING` + budget settings → Task 1 Step 7, Task 3 Step 7 ✓
- Drop `compute_cost_usd`, `BudgetExceeded`; sink → accumulator → Task 1 Step 4, Task 3 Step 6 ✓
- `services/run.py` budget handling (4 sites) → Task 1 Step 6 ✓
- Dashboard contract rename → Task 2 Steps 3-4, 8 ✓
- GDPR export drops `costUsd` → Task 2 Step 6 ✓
- Web renders tokens → Task 2 Steps 9-10 ✓
- Docs → Task 3 Step 12 ✓

**Type consistency:** `UsageRecord`/`UsageSink` are introduced in Task 3 Step 6 and consumed in Steps 8-9 with matching field names. Task 1 deliberately keeps the old `CostSink`/`CostRecord` names (renaming there would churn twice); Task 3 Step 6 notes that the Task 1 test must be updated to the new names. `RunOut.from_model(run, total_tokens=None)` defined in Task 2 Step 5 matches the dashboard call in Task 2 Step 4. `TokensByStage.total_tokens` / `TokenPoint.total_tokens` match the TS `totalTokens` via the camel alias generator.

**Known ordering caveat:** Task 2 leaves `run.cost_usd` written but unread; Task 3 removes the write and the column in the same commit. Between Task 2 and Task 3 the suite is green.
