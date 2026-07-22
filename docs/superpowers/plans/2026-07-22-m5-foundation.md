# M5 Foundation Lane — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the serial shared base for M5 (Hardening) — one Alembic migration, the cost-ledger model, config keys, the frozen `shared-types` contract, and pre-registered router/nav stubs — so the five fan-out lanes (OBS/NET/DATA/DASH/LOAD) branch from a merged foundation and never touch a coupling hub.

**Architecture:** Additive only. One new Alembic revision (`down_revision = b7d41e05a9c2`) creates the `llm_costs` per-user table (RLS-forced), adds `companies.opt_out`, and adds `runs.cost_usd`/`runs.duration_ms`. `shared-types/src/index.ts` gets one edit adding every M5 type. `routers/__init__.py` and `apps/web/src/lib/nav.ts` get the dashboard + account/settings entries once. The `targeting` vertical remains the copy-me template lanes clone.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (`Mapped`/`mapped_column`) · Alembic · Postgres 16 + pgvector · Pydantic v2 · pytest · Next.js 16 / TS strict.

## Global Constraints

- Python `>=3.12`; SQLAlchemy 2.0 declarative (`Mapped[...]` + `mapped_column`), never legacy `Column`. Models subclass `Base` (`specula_api.db.base`); FK/PK via `user_fk()`/`uuid_pk()` in `specula_api.db.columns`.
- **Exactly one Alembic revision for all of M5.** Its `down_revision = "b7d41e05a9c2"` (current head). No lane adds a second revision on a live branch.
- **Exactly one `packages/shared-types/src/index.ts` edit for all of M5** — this task. Lanes never touch it.
- New per-user table **must** get RLS (`ENABLE` + `FORCE ROW LEVEL SECURITY` + `tenant_isolation` policy) via the exact GUC form `nullif(current_setting('app.user_id', true), '')::uuid`. Omitting this is a tenancy hole.
- Services take `(session, user_id, ...)` and call `await session.flush()` — never `commit()`/`rollback()` (the session wrapper owns the transaction; a mid-request commit drops the `app.user_id` GUC → RLS breaks).
- API boundary is camelCase via the `CamelModel` base (`alias_generator=to_camel, populate_by_name=True`); match `packages/shared-types/src/index.ts`.
- Product invariants: counts DERIVED server-side; salary never ranks/filters; low-confidence excluded from Insights.
- Verify green: `cd apps/api && uv run pytest -q && uv run mypy . && uv run ruff check && uv run ruff format --check`; web `pnpm -C apps/web lint && pnpm -C apps/web typecheck`.
- Tests touching the DB: `from test_db import requires_db`, decorate with `@requires_db`, take the `migrated_db: None` fixture, and monkeypatch `settings.service_jwt_secret` before `mint(...)`.

---

### Task 1: `LlmCost` model (the cost ledger)

**Files:**
- Create: `apps/api/specula_api/db/models/llm_cost.py`
- Modify: `apps/api/specula_api/db/models/__init__.py`
- Test: `apps/api/tests/test_llm_cost_model.py`

**Interfaces:**
- Produces: `LlmCost` ORM model, `__tablename__ = "llm_costs"`, columns `id, user_id, run_id, company_id, stage, model, prompt_tokens, completion_tokens, embed_tokens, cost_usd, created_at`. OBS writes rows; DASH reads them; DATA cascades/export them.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_llm_cost_model.py
from specula_api.db.models import LlmCost


def test_llm_cost_table_and_columns() -> None:
    assert LlmCost.__tablename__ == "llm_costs"
    cols = set(LlmCost.__table__.columns.keys())
    assert cols == {
        "id", "user_id", "run_id", "company_id", "stage", "model",
        "prompt_tokens", "completion_tokens", "embed_tokens", "cost_usd", "created_at",
    }
    # tenancy FK cascades with the owning user
    fk = next(iter(LlmCost.__table__.c.user_id.foreign_keys))
    assert fk.ondelete == "CASCADE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_llm_cost_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'LlmCost'`.

- [ ] **Step 3: Write the model**

```python
# apps/api/specula_api/db/models/llm_cost.py
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import user_fk, uuid_pk


class LlmCost(Base):
    """Per-call OpenAI spend ledger. Written by the pipeline (OBS), read by the
    dashboard (DASH). run_id/company_id are informational (no FK): company ingest —
    the dominant spend — creates no Run, so cost cannot hang off `runs`. Tenancy is
    the user_id FK (CASCADE) alone; account deletion drops these rows."""

    __tablename__ = "llm_costs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    stage: Mapped[str] = mapped_column(Text)  # 'discovery'|'extract'|'embed'|'score'|'rationale'
    model: Mapped[str] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    embed_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Then in `apps/api/specula_api/db/models/__init__.py` add the import (alphabetical, after `Lens`):
```python
from specula_api.db.models.llm_cost import LlmCost
```
and `"LlmCost",` in `__all__` (after `"Lens"`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_llm_cost_model.py -v && uv run mypy specula_api/db/models/llm_cost.py`
Expected: PASS; mypy clean.

- [ ] **Step 5: Commit**

```bash
git add apps/api/specula_api/db/models/llm_cost.py apps/api/specula_api/db/models/__init__.py apps/api/tests/test_llm_cost_model.py
git commit -m "feat(m5-foundation): add LlmCost cost-ledger model"
```

---

### Task 2: Add `companies.opt_out` and `runs.cost_usd`/`runs.duration_ms` to models

**Files:**
- Modify: `apps/api/specula_api/db/models/company.py`, `apps/api/specula_api/db/models/run.py`
- Test: `apps/api/tests/test_llm_cost_model.py` (extend)

**Interfaces:**
- Produces: `Company.opt_out: bool` (per-company removal flag, default false → DATA/NET endpoint); `Run.cost_usd: Decimal | None`, `Run.duration_ms: int | None` (rollups OBS writes, DASH/RunOut read).

- [ ] **Step 1: Write the failing test** (append)

```python
def test_company_optout_and_run_rollups_exist() -> None:
    from specula_api.db.models import Company, Run
    assert "opt_out" in Company.__table__.columns
    assert Company.__table__.c.opt_out.nullable is False
    assert {"cost_usd", "duration_ms"} <= set(Run.__table__.columns.keys())
    assert Run.__table__.c.cost_usd.nullable is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_llm_cost_model.py::test_company_optout_and_run_rollups_exist -v`
Expected: FAIL — `AssertionError` / KeyError on `opt_out`.

- [ ] **Step 3: Add the columns**

In `company.py` after `tracking`:
```python
    opt_out: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
```
In `run.py` after `stats` (import `Integer`, `Numeric` from sqlalchemy; add `from decimal import Decimal`):
```python
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_llm_cost_model.py -v && uv run mypy specula_api/db/models`
Expected: PASS; mypy clean.

- [ ] **Step 5: Commit**

```bash
git add apps/api/specula_api/db/models/company.py apps/api/specula_api/db/models/run.py apps/api/tests/test_llm_cost_model.py
git commit -m "feat(m5-foundation): add companies.opt_out + runs cost/duration rollups"
```

---

### Task 3: The single M5 Alembic migration (llm_costs + RLS, opt_out, run rollups)

**Files:**
- Create: `apps/api/alembic/versions/<autogen>_m5_hardening_foundation.py`
- Test: `apps/api/tests/test_m5_migration.py`

**Interfaces:**
- Consumes: models from Tasks 1–2.
- Produces: schema at head `m5_hardening_foundation`, `down_revision = "b7d41e05a9c2"`; `llm_costs` RLS-forced with `tenant_isolation`; `companies.opt_out`; `runs.cost_usd`/`duration_ms`. Reverses cleanly.

- [ ] **Step 1: Generate the revision skeleton**

Run: `cd apps/api && uv run alembic revision -m "m5 hardening foundation"`
Then set `down_revision = "b7d41e05a9c2"` and author `upgrade()`/`downgrade()` (do NOT autogenerate — hand-write for the RLS policy):

```python
def upgrade() -> None:
    op.create_table(
        "llm_costs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("embed_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_costs_user_id"), "llm_costs", ["user_id"], unique=False)

    tenant = "nullif(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE llm_costs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE llm_costs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON llm_costs "
        f"USING (user_id = {tenant}) WITH CHECK (user_id = {tenant})"
    )

    op.add_column("companies", sa.Column("opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("runs", sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True))
    op.add_column("runs", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "duration_ms")
    op.drop_column("runs", "cost_usd")
    op.drop_column("companies", "opt_out")
    op.drop_index(op.f("ix_llm_costs_user_id"), table_name="llm_costs")
    op.drop_table("llm_costs")  # policy drops with the table
```

- [ ] **Step 2: Write the failing test**

```python
# apps/api/tests/test_m5_migration.py
import uuid

import pytest
from sqlalchemy import text

from specula_api.db.session import async_session
from test_db import requires_db


@requires_db
async def test_llm_costs_rls_fails_closed_without_guc(migrated_db: None) -> None:
    # No app.user_id set → RLS returns zero rows (fail-closed), never raises.
    async with async_session() as s:
        rows = (await s.execute(text("SELECT * FROM llm_costs"))).all()
        assert rows == []


@requires_db
async def test_llm_costs_scoped_by_tenant(migrated_db: None) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    async with async_session() as s:
        # seed two users so the FK holds
        for u in (a, b):
            await s.execute(text("INSERT INTO users (id, google_sub, email) VALUES (:i,:g,:e)"),
                            {"i": str(u), "g": str(u), "e": f"{u}@x.io"})
        await s.execute(text("SELECT set_config('app.user_id', :u, false)"), {"u": str(a)})
        await s.execute(text(
            "INSERT INTO llm_costs (user_id, stage, model, cost_usd) VALUES (:u,'score','gpt-4o-mini',0.01)"
        ), {"u": str(a)})
        await s.commit()
    async with async_session() as s:
        await s.execute(text("SELECT set_config('app.user_id', :u, false)"), {"u": str(b)})
        assert (await s.execute(text("SELECT * FROM llm_costs"))).all() == []  # B sees none of A's
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_m5_migration.py -v`
Expected: FAIL — table `llm_costs` does not exist (migration not applied yet).

- [ ] **Step 4: Apply the migration and verify up+down reverse cleanly**

```bash
just migrate            # apply as specula_app role
just migrate-down       # roll back one step — must succeed (policy drops with table)
just migrate            # re-apply for the tests
cd apps/api && uv run pytest tests/test_m5_migration.py -v
```
Expected: both migrate steps succeed; tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/*m5_hardening_foundation.py apps/api/tests/test_m5_migration.py
git commit -m "feat(m5-foundation): migration — llm_costs (RLS), opt_out, run rollups"
```

---

### Task 4: Config keys + OpenAI price map

**Files:**
- Modify: `apps/api/specula_api/config.py`
- Test: `apps/api/tests/test_config_m5.py`

**Interfaces:**
- Produces: `settings.openai_run_budget_usd`, `openai_daily_budget_usd`, `run_rate_limit_per_hour`, `run_cooldown_s`, `log_level`, `sentry_dsn`, `otel_enabled`; module constant `OPENAI_PRICING` (model → USD-per-1M tokens). OBS uses budgets + pricing to write costs/enforce caps; NET uses rate-limit keys; DASH imports `OPENAI_PRICING` for display parity.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_config_m5.py
from specula_api.config import OPENAI_PRICING, settings


def test_m5_settings_present() -> None:
    assert settings.openai_run_budget_usd > 0
    assert settings.openai_daily_budget_usd >= settings.openai_run_budget_usd
    assert settings.run_rate_limit_per_hour > 0
    assert settings.run_cooldown_s >= 0
    assert settings.log_level == "INFO"
    assert settings.sentry_dsn is None
    assert settings.otel_enabled is False


def test_pricing_covers_configured_models() -> None:
    for m in (settings.openai_search_model, settings.openai_extract_model,
              settings.openai_embed_model, settings.openai_rationale_model):
        assert m in OPENAI_PRICING
        assert {"prompt", "completion", "embed"} <= set(OPENAI_PRICING[m])
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_config_m5.py -v`
Expected: FAIL — `ImportError`/`AttributeError`.

- [ ] **Step 3: Add the keys + price map**

Add to the `Settings` class (after `pipeline_fixtures_dir`):
```python
    # --- M5 hardening ---
    openai_run_budget_usd: float = 5.0      # abort/mark a run/ingest if its LLM spend exceeds this
    openai_daily_budget_usd: float = 20.0   # per-user daily ceiling across runs
    run_rate_limit_per_hour: int = 10       # on-demand trigger cap (NET gate)
    run_cooldown_s: int = 60                # min seconds between a user's triggers
    log_level: str = "INFO"
    sentry_dsn: str | None = None           # None → Sentry disabled (live wiring deferred with hosting)
    otel_enabled: bool = False
```
Add a module-level constant near the bottom (above `settings = Settings()`). **Verify rates against current OpenAI pricing before going live; USD per 1M tokens:**
```python
# USD per 1,000,000 tokens. Embedding models bill only on `embed`.
OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"prompt": 2.50, "completion": 10.00, "embed": 0.0},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60, "embed": 0.0},
    "text-embedding-3-small": {"prompt": 0.0, "completion": 0.0, "embed": 0.02},
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_config_m5.py -v && uv run mypy specula_api/config.py`
Expected: PASS; mypy clean.

- [ ] **Step 5: Commit**

```bash
git add apps/api/specula_api/config.py apps/api/tests/test_config_m5.py
git commit -m "feat(m5-foundation): M5 config keys + OpenAI price map"
```

---

### Task 5: Extend `RunOut` with optional cost

**Files:**
- Modify: `apps/api/specula_api/schemas/run.py`
- Test: `apps/api/tests/test_run_schema_cost.py`

**Interfaces:**
- Produces: `RunOut.cost: RunCost | None` where `RunCost(cost_usd: float, duration_ms: int | None)`. Mirrors TS `Run.cost` (Task 6). DASH reads it; OBS populates the rollup.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_run_schema_cost.py
from datetime import UTC, datetime
from uuid import uuid4

from specula_api.schemas.run import RunCost, RunOut


def test_runout_serialises_cost_camel() -> None:
    out = RunOut(
        id=uuid4(), kind="on_demand", status="done",
        started_at=None, finished_at=None,
        stats={"found": 0, "new": 0, "closed": 0, "low_conf_excluded": 0, "errors": 0},
        created_at=datetime.now(UTC),
        cost=RunCost(cost_usd=1.25, duration_ms=4200),
    )
    dumped = out.model_dump(by_alias=True)
    assert dumped["cost"]["costUsd"] == 1.25
    assert dumped["cost"]["durationMs"] == 4200
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_run_schema_cost.py -v`
Expected: FAIL — `ImportError: RunCost` / unexpected kwarg `cost`.

- [ ] **Step 3: Implement**

In `schemas/run.py` add a `RunCost(CamelModel)` and a `cost` field, plus wire `from_model`:
```python
class RunCost(CamelModel):
    cost_usd: float
    duration_ms: int | None = None


class RunOut(CamelModel):
    id: UUID
    kind: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats: RunStats
    created_at: datetime
    cost: RunCost | None = None

    @classmethod
    def from_model(cls, run: Run) -> "RunOut":
        cost = (
            RunCost(cost_usd=float(run.cost_usd), duration_ms=run.duration_ms)
            if run.cost_usd is not None else None
        )
        return cls(
            id=run.id, kind=run.kind, status=run.status,
            started_at=run.started_at, finished_at=run.finished_at,
            stats=RunStats.model_validate(run.stats), created_at=run.created_at,
            cost=cost,
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_run_schema_cost.py tests/test_run_api.py -v && uv run mypy specula_api/schemas/run.py`
Expected: PASS (existing run-api tests still green — `cost` defaults to `None`); mypy clean.

- [ ] **Step 5: Commit**

```bash
git add apps/api/specula_api/schemas/run.py apps/api/tests/test_run_schema_cost.py
git commit -m "feat(m5-foundation): optional cost on RunOut"
```

---

### Task 6: Freeze the `shared-types` contract (single edit)

**Files:**
- Modify: `packages/shared-types/src/index.ts`
- Test: `apps/web` typecheck (contract is compile-time)

**Interfaces:**
- Produces the frozen TS contract every lane builds against: `LlmCost`, `RunCost` + `Run.cost`, `CostPoint`, `DashboardSummary` (OBS→DASH behavioral contract), `ExportBundle` (DATA), `RateLimitError` (NET).

- [ ] **Step 1: Add the interfaces**

Append to `index.ts` (match the existing flat `export interface` style, camelCase):
```typescript
export interface LlmCost {
  id: string; runId: string | null; companyId: string | null;
  stage: string; model: string;
  promptTokens: number; completionTokens: number; embedTokens: number;
  costUsd: number; createdAt: string;
}
export interface RunCost { costUsd: number; durationMs: number | null }
export interface CostPoint { date: string; costUsd: number; runs: number }
export interface CostByStage { stage: string; costUsd: number }
export interface DashboardSummary {
  totalCostUsd: number; runCount: number;
  costByStage: CostByStage[]; costByDay: CostPoint[]; recentRuns: Run[];
}
// A data-export blob is a heterogeneous dump; DATA owns the row shapes on both ends,
// so arrays are intentionally `unknown[]` here (a deliberate type, not a placeholder).
export interface ExportBundle {
  exportedAt: string;
  candidate: unknown; targeting: unknown;
  companies: unknown[]; postings: unknown[]; scores: unknown[];
  lenses: unknown[]; runs: unknown[]; llmCosts: LlmCost[];
}
export interface RateLimitError { error: "rate_limited"; retryAfterS: number }
```
Then extend the existing `Run` interface with one field:
```typescript
  stats: RunStats; createdAt: string; cost?: RunCost | null;
```

- [ ] **Step 2: Typecheck the workspace**

Run: `pnpm -C apps/web typecheck && pnpm -C packages/shared-types run build`
Expected: PASS (additive; `cost?` optional keeps all 40 importers valid).

- [ ] **Step 3: Commit**

```bash
git add packages/shared-types/src/index.ts
git commit -m "feat(m5-foundation): freeze M5 shared-types contract"
```

---

### Task 7: Pre-register `dashboard` + `account` router stubs

**Files:**
- Create: `apps/api/specula_api/routers/dashboard.py`, `apps/api/specula_api/routers/account.py`
- Modify: `apps/api/specula_api/routers/__init__.py`
- Test: `apps/api/tests/test_router_stubs.py`

**Interfaces:**
- Produces: registered empty `APIRouter`s at prefixes `/dashboard` and `/account`. DASH fills `dashboard.py`; DATA fills `account.py`. Neither lane edits `routers/__init__.py` again.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_router_stubs.py
from specula_api.main import create_app


def test_dashboard_and_account_routers_registered() -> None:
    paths = {r.path for r in create_app().routes}  # type: ignore[attr-defined]
    assert "/api/v1/dashboard" in paths
    assert "/api/v1/account" in paths
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_router_stubs.py -v`
Expected: FAIL — paths absent.

- [ ] **Step 3: Create the stubs + register**

```python
# apps/api/specula_api/routers/dashboard.py
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard_root() -> dict[str, str]:
    """Stub filled by the DASH lane."""
    return {"status": "not_implemented"}
```
```python
# apps/api/specula_api/routers/account.py
from fastapi import APIRouter

router = APIRouter(prefix="/account", tags=["account"])


@router.get("")
async def account_root() -> dict[str, str]:
    """Stub filled by the DATA lane."""
    return {"status": "not_implemented"}
```
In `routers/__init__.py` add `account, dashboard` to the import tuple (alphabetical) and:
```python
api_router.include_router(account.router)
api_router.include_router(dashboard.router)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_router_stubs.py -v && uv run mypy specula_api/routers && uv run ruff check specula_api/routers`
Expected: PASS; clean.

- [ ] **Step 5: Commit**

```bash
git add apps/api/specula_api/routers/dashboard.py apps/api/specula_api/routers/account.py apps/api/specula_api/routers/__init__.py apps/api/tests/test_router_stubs.py
git commit -m "feat(m5-foundation): register dashboard + account router stubs"
```

---

### Task 8: Pre-register `dashboard` + `settings` nav entries

**Files:**
- Modify: `apps/web/src/lib/nav.ts` (and the icon-render map that consumes `IconName`)
- Test: `apps/web/src/lib/nav.test.ts`

**Interfaces:**
- Produces: `IconName` gains `"dashboard" | "settings"`; `NAV` gains a `dashboard` item (Intelligence) and a `settings` item (Configure). DASH builds `/dashboard`, DATA builds `/settings`; neither edits `nav.ts` again.

- [ ] **Step 1: Write the failing test**

```typescript
// apps/web/src/lib/nav.test.ts
import { describe, expect, it } from "vitest";
import { NAV, type NavItem } from "./nav";

describe("nav M5 entries", () => {
  const items = NAV.filter((e): e is NavItem => "id" in e);
  it("has dashboard and settings", () => {
    const ids = items.map((i) => i.id);
    expect(ids).toContain("dashboard");
    expect(ids).toContain("settings");
    expect(items.find((i) => i.id === "settings")?.href).toBe("/settings");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm -C apps/web test -- nav.test.ts`
Expected: FAIL — ids absent.

- [ ] **Step 3: Implement**

In `nav.ts` extend the union: `| "dashboard"` and `| "settings"`. Add to `NAV`: under `"Intelligence"` a `{ id: "dashboard", label: "Dashboard", href: "/dashboard", icon: "dashboard" }`, and under `"Configure"` a `{ id: "settings", label: "Settings", href: "/settings", icon: "settings" }`. Add matching entries to whichever `Record<IconName, ...>` icon map renders the sidebar (search `IconName` under `apps/web/src/components/`) so TS strict is satisfied — use any existing icon glyph as a placeholder-free stand-in (e.g. reuse the `insights`/`targeting` glyphs) and note in the lane briefs that final icons are a DASH/DATA polish detail.

- [ ] **Step 4: Run to verify it passes**

Run: `pnpm -C apps/web test -- nav.test.ts && pnpm -C apps/web typecheck`
Expected: PASS; typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/nav.ts apps/web/src/lib/nav.test.ts apps/web/src/components
git commit -m "feat(m5-foundation): register dashboard + settings nav entries"
```

---

### Task 9: Full-foundation verification gate

**Files:** none (verification only).

- [ ] **Step 1: Run the full API + web gate**

```bash
just migrate && just migrate-down && just migrate   # reversibility proven
cd apps/api && uv run pytest -q && uv run mypy . && uv run ruff check && uv run ruff format --check
pnpm -C apps/web lint && pnpm -C apps/web typecheck && pnpm -C apps/web test
```
Expected: all green. This is the branch-CI-parity gate for the foundation before any lane branches.

- [ ] **Step 2: Push and confirm branch-CI-green**

```bash
git push -u origin m5-foundation
```
Wait for GitHub Actions `ci.yml` (api + web jobs) to pass on the branch, then merge to `main`. **No lane branches until this is merged.**

---

## Self-Review

- **Spec coverage:** Foundation covers every hub edit named in the design's "Foundation lane" section — `llm_costs` + RLS (Task 1/3), `companies.opt_out` (Task 2/3), `runs` rollups (Task 2/3), config keys + price map (Task 4), `RunOut.cost` (Task 5), frozen shared-types (Task 6), router stubs (Task 7), nav entries (Task 8). The lane features (OBS/NET/DATA/DASH/LOAD) are out of scope here by design — they live in the per-lane briefs.
- **Placeholder scan:** `OPENAI_PRICING` carries a "verify current rates" note (real numbers, not a placeholder); `ExportBundle` uses `unknown[]` deliberately (documented). No TODO/TBD.
- **Type consistency:** `RunCost` fields (`cost_usd`/`duration_ms`) match TS `RunCost` (`costUsd`/`durationMs`); `LlmCost` columns match the TS `LlmCost` interface field-for-field; `runs.cost_usd`/`duration_ms` match `RunCost.from_model`.

## Execution Handoff

This foundation lane is executed **inline in the driver session** (it is the serial base, not a fan-out lane), then merged before Phase 2. Recommended sub-skill: **superpowers:subagent-driven-development** (fresh subagent per task, review between). After merge, the five lane briefs (`m5-*-brief.md`) fan out per `m5-fanout-playbook.md`.
