# Cheaper, controllable discovery — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut discovery cost/time (fewer, combined searches on a cheaper model, plus a query-exhaustion cache that parks played-out searches) and expose a per-user search cap in the UI.

**Architecture:** Pure-function change to the query builder (synonym collapse), a config/model swap, a new per-user `discovery_query_stat` table driving a skip-filter inside `discover()`, a `discovery_max_searches` column on `user_settings` read at run time, and a small settings endpoint + Settings-page section to edit it. Mirrors the existing `tweaks` CRUD stack throughout.

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 · Alembic · pytest (api); Next 16 · React 19 · Vitest (web). Design doc: `docs/superpowers/specs/2026-07-25-cheaper-discovery-design.md`.

## Global Constraints

- **Salary/counts invariants unaffected** — this touches discovery only.
- **RLS:** every new per-user table is `ENABLE`+`FORCE ROW LEVEL SECURITY` with the `tenant_isolation` policy `USING (user_id = nullif(current_setting('app.user_id', true), '')::uuid)` (mirror `alembic/versions/5f2f2fb3a1af_*.py:50-56`).
- **Per-user cap range 1–20; global default 10.** A `NULL` per-user value means "use the global default".
- **Seeds always run** — the exhaustion cache parks only auto-generated combined-role queries, never user lens seeds.
- **`mypy --strict` + `ruff` clean (api); `tsc` + `eslint` + `prettier` clean (web).** Camel/snake: API wire uses `CamelModel` (mirror `schemas/tweaks.py`).
- **Do NOT `git add -A`** — the working tree has unrelated user changes in `candidate-view`/`targeting-view`. Stage only the files each task lists.

---

## File structure

**API**
- `specula_api/config.py` — add `openai_discovery_model`; change `discovery_max_searches` default 20→10.
- `specula_api/pipeline/openai_client.py` — discover_sources uses `openai_discovery_model`.
- `specula_api/pipeline/discovery.py` — new `build_seed_queries` (returns typed queries), exhaustion filter + stat recording in `discover()`.
- `specula_api/db/models/discovery_query_stat.py` (new) + `user_settings.py` (add column) + `models/__init__.py`.
- `specula_api/alembic/versions/<rev>_cheaper_discovery.py` (new migration).
- `specula_api/services/discovery_settings.py` (new) — get/set per-user cap.
- `specula_api/schemas/discovery_settings.py` (new) + `routers/discovery_settings.py` (new) + `routers/__init__.py`.
- Tests: `tests/test_discovery.py`, `tests/test_discovery_query_stat.py` (new), `tests/test_discovery_settings_api.py` (new).

**Web**
- `src/lib/api/discovery-settings.ts` (new) — get/save.
- `src/app/api/settings/discovery/route.ts` (new) — BFF GET+PUT.
- `src/components/settings/settings-view.tsx` — new "Discovery" section.
- `src/components/settings/discovery-settings.tsx` (new) — the control.
- Tests: `discovery-settings.test.tsx` (new); extend `settings-view.test.tsx`.

---

## Task 1: Discovery model + default cap (config)

**Files:**
- Modify: `apps/api/specula_api/config.py`
- Modify: `apps/api/specula_api/pipeline/openai_client.py` (the live `discover_sources`/`_search` model arg)
- Test: `apps/api/tests/test_config_m5.py` (or a new assertion)

**Interfaces:**
- Produces: `settings.openai_discovery_model: str` (default `"gpt-4o-mini"`); `settings.discovery_max_searches: int = 10`.

- [ ] **Step 1: Failing test** — in `tests/test_config_m5.py`, add:
```python
def test_discovery_defaults() -> None:
    from specula_api.config import Settings

    s = Settings()
    assert s.discovery_max_searches == 10
    assert s.openai_discovery_model == "gpt-4o-mini"
```
- [ ] **Step 2: Run** `uv run pytest tests/test_config_m5.py -q` → FAIL (attr missing / value 20).
- [ ] **Step 3: Implement** — in `config.py`, change `discovery_max_searches: int = 10` and add below `openai_search_model`:
```python
    # Discovery only harvests source URLs (no reasoning), so it uses the cheap model.
    openai_discovery_model: str = "gpt-4o-mini"
```
Confirm `gpt-4o-mini` already exists in `OPENAI_PRICING` (it does).
- [ ] **Step 4:** In `openai_client.py`, the live `discover_sources` search call currently reads `self._settings.openai_search_model` (~line 179). Change that one call site to `self._settings.openai_discovery_model`. Leave `openai_search_model` for any other caller.
- [ ] **Step 5: Run** `uv run pytest tests/test_config_m5.py tests/test_metering.py -q` → PASS; `uv run mypy specula_api/config.py specula_api/pipeline/openai_client.py`.
- [ ] **Step 6: Commit** `apps/api/specula_api/config.py apps/api/specula_api/pipeline/openai_client.py apps/api/tests/test_config_m5.py`.

---

## Task 2: Synonym collapse — one combined role search per lens

Rewrite `build_seed_queries` to return **typed** queries (so Task 5 can exempt seeds): active-lens seeds (verbatim, `exhaustible=False`), then **one combined role query per active lens** (all role titles joined, `exhaustible=True`). Dedup; cap.

**Files:**
- Modify: `apps/api/specula_api/pipeline/discovery.py`
- Test: `apps/api/tests/test_discovery.py`

**Interfaces:**
- Produces:
```python
@dataclass(frozen=True)
class SeedQuery:
    text: str
    exhaustible: bool  # False for user lens seeds; True for generated role queries

def build_seed_queries(role_titles: list[str], lenses: list[Lens], *, cap: int) -> list[SeedQuery]: ...
```
- Consumes: `_region_hint(lens)` (unchanged), `Lens.seeds`, `Lens.active`.

- [ ] **Step 1: Failing tests** — replace the existing `build_seed_queries` tests in `test_discovery.py` (the ones asserting per-role×lens output) with:
```python
def test_build_seed_queries_one_combined_role_query_per_lens() -> None:
    lens = _lens(name="Remote EU", scope="Remote EU", seeds=[], active=True)
    out = build_seed_queries(["ML Engineer", "Data Scientist"], [lens], cap=10)
    assert out == [
        SeedQuery("ML Engineer / Data Scientist jobs remote EU", exhaustible=True),
    ]

def test_build_seed_queries_seeds_first_verbatim_and_not_exhaustible() -> None:
    lens = _lens(name="Spain", scope="ES", seeds=["fintech ML Madrid"], active=True)
    out = build_seed_queries(["ML Engineer"], [lens], cap=10)
    assert out[0] == SeedQuery("fintech ML Madrid", exhaustible=False)
    assert out[1] == SeedQuery("ML Engineer jobs Spain", exhaustible=True)

def test_build_seed_queries_combined_query_spans_lenses() -> None:
    de = _lens(name="DE", scope="DE", seeds=[], active=True)
    es = _lens(name="ES", scope="ES", seeds=[], active=True)
    out = build_seed_queries(["ML Engineer", "AI Engineer"], [de, es], cap=10)
    assert [q.text for q in out] == [
        "ML Engineer / AI Engineer jobs Germany",
        "ML Engineer / AI Engineer jobs Spain",
    ]

def test_build_seed_queries_respects_cap() -> None:
    lenses = [_lens(name=f"L{i}", scope="ES", seeds=[f"seed{i}"], active=True) for i in range(5)]
    out = build_seed_queries(["ML Engineer"], lenses, cap=3)
    assert len(out) == 3

def test_build_seed_queries_only_active_lenses() -> None:
    on = _lens(name="ES", scope="ES", seeds=[], active=True)
    off = _lens(name="DE", scope="DE", seeds=[], active=False)
    out = build_seed_queries(["ML Engineer"], [on, off], cap=10)
    assert [q.text for q in out] == ["ML Engineer jobs Spain"]
```
Add a `_lens(...)` helper if not present (constructs an in-memory `Lens`). Delete the now-obsolete per-role×lens assertions (they encode the old behavior — this is an intentional behavior change; if the plan's reviewer flags the deletion, that's expected).
- [ ] **Step 2: Run** `uv run pytest tests/test_discovery.py -k build_seed_queries -q` → FAIL.
- [ ] **Step 3: Implement** — replace `build_seed_queries` (keep `_region_hint`):
```python
@dataclass(frozen=True)
class SeedQuery:
    text: str
    exhaustible: bool


def build_seed_queries(
    role_titles: list[str], lenses: list[Lens], *, cap: int
) -> list[SeedQuery]:
    """Effective ATS job-board searches, deduped and capped. Each active lens's own seeds run
    first, verbatim (never parked by the exhaustion cache). Then ONE combined role query per
    active lens — the role titles are near-synonyms, so a single search per lens finds the same
    companies as one-per-title at a fraction of the cost. The web_search tool is domain-filtered
    to ATS hosts, so a query only needs the roles + a location cue."""
    active = [lens for lens in lenses if lens.active]
    out: list[SeedQuery] = []
    seen: set[str] = set()

    def _add(text: str, *, exhaustible: bool) -> bool:
        text = text.strip()
        if text and text not in seen:
            seen.add(text)
            out.append(SeedQuery(text, exhaustible))
        return len(out) >= cap

    for lens in active:
        for seed in lens.seeds:
            if _add(seed, exhaustible=False):
                return out
    roles = " / ".join(r.strip() for r in role_titles if r.strip())
    if roles:
        for lens in active:
            combined = " ".join(p for p in (roles, "jobs", _region_hint(lens)) if p)
            if _add(combined, exhaustible=True):
                return out
    return out
```
- [ ] **Step 4: Run** `uv run pytest tests/test_discovery.py -q` → PASS (some `discover()` tests also updated in Task 5; if they fail on the SeedQuery type now, mark them and fix in Task 5). `uv run mypy specula_api/pipeline/discovery.py`.
- [ ] **Step 5: Commit** `apps/api/specula_api/pipeline/discovery.py apps/api/tests/test_discovery.py`.

---

## Task 3: DB — per-user cap column + `discovery_query_stat` table + migration

**Files:**
- Modify: `apps/api/specula_api/db/models/user_settings.py`
- Create: `apps/api/specula_api/db/models/discovery_query_stat.py`
- Modify: `apps/api/specula_api/db/models/__init__.py`
- Create: `apps/api/alembic/versions/<rev>_cheaper_discovery.py`
- Test: `apps/api/tests/test_models.py` (or new `test_discovery_query_stat.py` Task 5 covers behavior)

**Interfaces:**
- Produces: `UserSettings.discovery_max_searches: Mapped[int | None]`; model `DiscoveryQueryStat(user_id, query, last_run_at, consecutive_empty_runs)`.

- [ ] **Step 1:** Add to `user_settings.py`:
```python
    discovery_max_searches: Mapped[int | None] = mapped_column(Integer, nullable=True)
```
(add `Integer` to the sqlalchemy import).
- [ ] **Step 2:** Create `discovery_query_stat.py` (mirror the column helpers used by other models — `user_fk`, `TimestampMixin`, `Base`):
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import TimestampMixin, user_fk


class DiscoveryQueryStat(TimestampMixin, Base):
    """Per-user memory of how a discovery query has been performing, so played-out searches
    (all their companies already known) get parked instead of re-paid every run."""

    __tablename__ = "discovery_query_stat"

    user_id: Mapped[uuid.UUID] = user_fk(primary_key=True)
    query: Mapped[str] = mapped_column(Text, primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consecutive_empty_runs: Mapped[int] = mapped_column(Integer, server_default=text("0"))
```
- [ ] **Step 3:** Export it in `db/models/__init__.py` (add the import + `__all__` entry, matching the existing pattern).
- [ ] **Step 4:** New Alembic migration (`down_revision` = current head — find via `uv run alembic heads`). `upgrade()`:
```python
    op.add_column(
        "user_settings",
        sa.Column("discovery_max_searches", sa.Integer(), nullable=True),
    )
    op.create_table(
        "discovery_query_stat",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "consecutive_empty_runs", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "query"),
    )
    tenant = "nullif(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE discovery_query_stat ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE discovery_query_stat FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON discovery_query_stat "
        f"USING (user_id = {tenant}) WITH CHECK (user_id = {tenant})"
    )
```
`downgrade()` drops the table and the column. (Confirm `TimestampMixin` provides `created_at`/`updated_at`; if it only provides one, match the migration columns to the mixin.)
- [ ] **Step 5: Run** `uv run alembic upgrade head` against the local DB (`just up` first if needed) → succeeds; `uv run alembic downgrade -1 && uv run alembic upgrade head` round-trips. `uv run mypy specula_api/db`.
- [ ] **Step 6: Commit** the model files, `__init__.py`, and the migration.

---

## Task 4: Per-user cap read in `discover()`

**Files:**
- Create: `apps/api/specula_api/services/discovery_settings.py`
- Modify: `apps/api/specula_api/pipeline/discovery.py` (use it as the cap)
- Test: `apps/api/tests/test_discovery.py`

**Interfaces:**
- Produces: `async def effective_max_searches(session, user_id, settings) -> int` — the user's `UserSettings.discovery_max_searches` clamped to 1–20, or `settings.discovery_max_searches` when `NULL`.

- [ ] **Step 1: Failing test** (`test_discovery.py`): a user with `UserSettings(discovery_max_searches=3)` → `effective_max_searches` returns 3; with `NULL`/no row → returns `settings.discovery_max_searches` (10); a stored 99 clamps to 20; a stored 0 clamps to 1.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `discovery_settings.py`:
```python
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.config import Settings
from specula_api.db.models import UserSettings

MIN_SEARCHES, MAX_SEARCHES = 1, 20


async def effective_max_searches(
    session: AsyncSession, user_id: UUID, settings: Settings
) -> int:
    row = await session.get(UserSettings, user_id)
    value = row.discovery_max_searches if row is not None else None
    if value is None:
        return settings.discovery_max_searches
    return max(MIN_SEARCHES, min(MAX_SEARCHES, value))
```
- [ ] **Step 4:** In `discover()`, replace `cap=deps.settings.discovery_max_searches` with `cap=await effective_max_searches(session, user_id, deps.settings)`.
- [ ] **Step 5: Run** `uv run pytest tests/test_discovery.py -q`; `uv run mypy .`.
- [ ] **Step 6: Commit** the new service, `discovery.py`, and the test.

---

## Task 5: Query-exhaustion cache — filter + record in `discover()`

**Files:**
- Modify: `apps/api/specula_api/pipeline/discovery.py`
- Create: `apps/api/tests/test_discovery_query_stat.py`

**Interfaces:**
- Consumes: `SeedQuery` (Task 2), `DiscoveryQueryStat` (Task 3).
- Behavior constants: `_EXHAUSTION_THRESHOLD = 2`, `_COOLDOWN = timedelta(days=7)`.

- [ ] **Step 1: Failing tests** (`test_discovery_query_stat.py`, `@requires_db`), covering:
  1. An exhaustible query with `consecutive_empty_runs >= 2` and `last_run_at` within 7 days is **skipped** (its `discover_sources` is never called).
  2. The same query with `last_run_at` older than 7 days **runs** (retry).
  3. A **seed** (`exhaustible=False`) always runs even when a stat row says it's exhausted.
  4. After a run, a query that found ≥1 new company has `consecutive_empty_runs` reset to 0; one that found 0 new has it incremented; `last_run_at` updated for both.
  Use a stub `OpenAIClient` (mirror `test_discovery.py`'s) to record which queries were searched.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** in `discovery.py`:
  - Add helpers:
```python
_EXHAUSTION_THRESHOLD = 2
_COOLDOWN = timedelta(days=7)


async def _exhausted(session: AsyncSession, user_id: UUID, now: datetime) -> set[str]:
    """Query texts to skip this run: emptied out (>= threshold) and still inside the cooldown."""
    rows = await session.scalars(
        select(DiscoveryQueryStat).where(DiscoveryQueryStat.user_id == user_id)
    )
    return {
        r.query
        for r in rows
        if r.consecutive_empty_runs >= _EXHAUSTION_THRESHOLD and now - r.last_run_at < _COOLDOWN
    }


async def _record_query_stats(
    session: AsyncSession, user_id: UUID, new_by_query: dict[str, int], now: datetime
) -> None:
    for query, new_count in new_by_query.items():
        stat = await session.get(DiscoveryQueryStat, (user_id, query))
        if stat is None:
            stat = DiscoveryQueryStat(user_id=user_id, query=query)
            session.add(stat)
        stat.last_run_at = now
        stat.consecutive_empty_runs = 0 if new_count > 0 else stat.consecutive_empty_runs + 1
```
  - In `discover()`: after building the capped `SeedQuery` list, compute `skip = await _exhausted(session, user_id, deps.now())` and iterate only queries where `not (q.exhaustible and q.text in skip)`. Track `new_by_query[q.text]` as the count of *new* candidates staged for that query (increment where the loop currently does `new += 1`). After the loop (before/with the flush), call `await _record_query_stats(session, user_id, new_by_query, deps.now())` for every query that actually ran.
  - Note: `deps.now` exists on `PipelineDeps` (used by scoring) — use it for testability.
- [ ] **Step 4:** Update the existing `discover()` tests in `test_discovery.py` for the new `SeedQuery` return type (queries are `.text`) and the added stat writes.
- [ ] **Step 5: Run** `uv run pytest tests/test_discovery.py tests/test_discovery_query_stat.py -q`; `uv run mypy .`.
- [ ] **Step 6: Commit** `discovery.py` + the two test files.

---

## Task 6: Discovery-settings API endpoint

Mirror the `tweaks` stack (`routers/tweaks.py`, `schemas/tweaks.py`, `services/tweaks.py`).

**Files:**
- Create: `apps/api/specula_api/schemas/discovery_settings.py`, `services/discovery_settings.py` (extend Task 4's file), `routers/discovery_settings.py`
- Modify: `apps/api/specula_api/routers/__init__.py`
- Test: `apps/api/tests/test_discovery_settings_api.py`

**Interfaces:**
- `GET /api/v1/settings/discovery` → `{ "maxSearches": <int|null-as-default> }`; `PUT` body `{ "maxSearches": 1..20 }` → persisted echo.

- [ ] **Step 1: Failing API test** (`ASGITransport`, mirror `test_approvals_api.py` auth): GET before any set returns the global default (10); PUT 7 persists; GET returns 7; PUT 0 and PUT 99 → 422 (validated 1–20).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**
  - `schemas/discovery_settings.py`:
```python
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DiscoverySettingsIn(CamelModel):
    max_searches: int = Field(ge=1, le=20)


class DiscoverySettingsOut(CamelModel):
    max_searches: int
```
  - In `services/discovery_settings.py` add `get_max_searches_out` (returns effective int) and `set_max_searches(session, user_id, value)` (upsert `UserSettings.discovery_max_searches`; create the row if missing, mirror `upsert_tweaks`). Reuse `effective_max_searches` for the GET value.
  - `routers/discovery_settings.py`: `prefix="/settings/discovery"`, GET + PUT mirroring `routers/tweaks.py`. Register in `routers/__init__.py`.
- [ ] **Step 4: Run** `uv run pytest tests/test_discovery_settings_api.py -q`; `uv run mypy .`; `uv run ruff check`.
- [ ] **Step 5: Commit** the schema, service, router, `__init__.py`, and test.

---

## Task 7: Frontend — Settings "Discovery" section

**Files:**
- Create: `apps/web/src/lib/api/discovery-settings.ts`
- Create: `apps/web/src/app/api/settings/discovery/route.ts`
- Create: `apps/web/src/components/settings/discovery-settings.tsx`
- Modify: `apps/web/src/components/settings/settings-view.tsx`
- Test: `apps/web/src/components/settings/discovery-settings.test.tsx` (new); extend `settings-view.test.tsx`
- Modify: `apps/web/src/lib/api/test-fixtures.ts` (mock `/settings/discovery`)

**Interfaces:**
- `getDiscoverySettings(): Promise<{ maxSearches: number }>` (server, `bffFetch`); `saveDiscoverySettings(maxSearches: number): Promise<void>` (client, POST/PUT via BFF route).

- [ ] **Step 1:** BFF route `src/app/api/settings/discovery/route.ts` — GET and PUT proxying to `/settings/discovery` (mirror `src/app/api/companies/[id]/route.ts` for the `bffFetch` proxy shape; PUT forwards the JSON body).
- [ ] **Step 2:** `src/lib/api/discovery-settings.ts` — `getDiscoverySettings` (server, `bffFetch<{maxSearches:number}>("/settings/discovery")`) and `saveDiscoverySettings` (client `fetch("/api/settings/discovery", {method:"PUT", ...})`, throw on non-ok — mirror `saveCandidate`).
- [ ] **Step 3:** `discovery-settings.tsx` (client) — a number input or `<input type=range min=1 max=20>` bound to state seeded from a prop, a **Save** button (disabled until changed), and a hint line: `` `≈ $${(0.02 * n).toFixed(2)} and ~${n * 7}s per run` `` (rough, derived from the measured ~$0.02 & ~7s per search). On save call `saveDiscoverySettings`; show "Saved."/error like `RescoreButton`.
- [ ] **Step 4:** `settings-view.tsx` — make it accept `initialMaxSearches: number` (Settings page fetches it via `getDiscoverySettings`), and render `<DiscoverySettings initial={initialMaxSearches} />` in a new `<section>` styled like the existing "Export your data" block, above "Delete account". Update `settings/page.tsx` to fetch + pass it.
- [ ] **Step 5: Tests** — `discovery-settings.test.tsx`: renders the current value; Save PUTs `/api/settings/discovery` with the chosen number; disabled until changed; surfaces an error. Extend `settings-view.test.tsx` for the new section heading. Add a `/settings/discovery` branch to `mockBffFetch` in `test-fixtures.ts`.
- [ ] **Step 6: Run** `pnpm exec tsc --noEmit`; `pnpm exec vitest run src/components/settings src/lib/api`; `pnpm lint`.
- [ ] **Step 7: Commit** the new files + `settings-view.tsx` + `settings/page.tsx` + `test-fixtures.ts`.

---

## Task 8: Live A/B validation (gate before final merge)

Not a code task — a verification checkpoint. Run against a real account (`joris`, live OpenAI) and compare old vs new.

- [ ] **Step 1:** On `main`@pre-change, trigger one discovery run; record the set of company domains found + `cost_usd` (from the `runs` row / `llm_costs`).
- [ ] **Step 2:** On this branch, trigger one discovery run for the same user; record the same.
- [ ] **Step 3: Compare** — new run should (a) cost materially less (fewer calls × mini) and (b) surface a comparable set of relevant companies (allow some variance — web_search is non-deterministic). If coverage drops badly, apply the spec's §1 fallback (cap distinct role searches at 2–3 instead of one combined query) and/or revisit the model, then re-run.
- [ ] **Step 4:** Record the before/after numbers in the PR/commit message.

---

## Self-review (done by author)

- **Spec coverage:** synonym collapse (T2), mini model (T1), exhaustion cache (T3 table + T5 logic), UI-controllable cap (T3 column + T4 read + T6 API + T7 UI), A/B gate (T8). ✅ all four + validation.
- **Type consistency:** `SeedQuery` introduced in T2 and consumed in T5; `effective_max_searches` defined T4, reused T6; `DiscoveryQueryStat` created T3, used T5. ✅
- **Placeholder scan:** concrete code for all logic; CRUD/UI steps name exact files + the pattern to mirror with paths. The only "find the value" is `down_revision` (T3, via `alembic heads`) — inherent to migrations.
- **Ordering:** config → pure builder → schema/migration → cap read → exhaustion → API → UI → validate. Each task independently testable.
