# M5 Fan-out Lane Playbook (read this first)

Shared instructions for every M5 hardening lane. Your per-lane brief (`m5-<lane>-brief.md`)
names the files you own, the endpoints/behavior, and your done-criteria; this playbook is
the *how*. You are in a git worktree on branch `m5-<lane>` with your own database
(`specula_wt_<lane>`, already migrated + seeded). Postgres is on host port **55432**; you
connect as the non-superuser `specula_app` role (this is what makes RLS actually bind — a
superuser silently bypasses `FORCE ROW LEVEL SECURITY`).

## The foundation you build on (already merged to `main`, you branched from it)

- **Cost ledger:** `LlmCost` model (`specula_api.db.models` → `llm_costs`), RLS-forced.
- **New columns:** `companies.opt_out` (bool, default false), `runs.cost_usd`/`runs.duration_ms`.
- **Config:** `settings.openai_run_budget_usd`, `openai_daily_budget_usd`,
  `run_rate_limit_per_hour`, `run_cooldown_s`, `log_level`, `sentry_dsn`, `otel_enabled`;
  the `OPENAI_PRICING` constant (model → USD/1M tokens) in `specula_api.config`.
- **Contract (frozen — DO NOT edit `packages/shared-types/src/index.ts`):** `LlmCost`,
  `RunCost` (+ `Run.cost`), `CostPoint`, `CostByStage`, `DashboardSummary`, `ExportBundle`,
  `RateLimitError`. Your Python schemas must serialize to match these camelCase shapes.
- **Registered stubs:** `routers/dashboard.py` + `routers/account.py` (empty routers, already
  in `routers/__init__.py`); nav entries `dashboard` + `settings` (already in `lib/nav.ts`).
- **Copy-me template:** the `targeting` vertical — `schemas/targeting.py` (the `CamelModel`
  base), `services/targeting.py` (session/user_id + `flush()`), `routers/targeting.py`
  (`Depends(get_current_user_id)` + `Depends(get_session)`), `tests/test_targeting_api.py`.
  Clone its shape for any new slice.

## The dividing rule — you own a disjoint file set

Your brief lists the files you own. **Touch only those.** The whole point of the foundation
was to move every shared hub edit out of the lanes. If you find yourself needing to edit
`shared-types/index.ts`, add an Alembic revision, or edit `routers/__init__.py` /
`services/run.py` (if it isn't yours) / `config.py` / `nav.ts` / `bff.ts` — **STOP**, write
it to your `.lane-status.md` as a blocked/shared-surface item, and flag the integrator. It
becomes a one-file serialized amendment, not a lane edit.

Two files that look shared but aren't — know which is yours:
- **`services/run.py` (OBS only) vs `routers/run.py` (NET only).** Do not cross.
- **`pipeline/deps.py` (OBS) ↔ `PoliteFetcher` in `pipeline/http.py` (NET).** If you are NET,
  keep `PoliteFetcher(settings)`'s constructor signature stable (add tunables via `Settings`,
  never new positional args) — OBS's `deps.py` constructs it.

## Hard rules (a reviewer will reject violations)

1. **Never expose or accept `user_id`** in a schema. It comes from the JWT.
2. **Services `flush()`, never `commit()`/`rollback()`** — the session wrapper owns the
   transaction. Off-request/background code opens `async with tenant_session(user_id)` (sets
   the `app.user_id` GUC); on-request handlers use `Depends(get_session)`.
3. **Scope every query by `user_id`** in the service (belt-and-suspenders alongside RLS).
4. **camelCase at the API boundary** via the `CamelModel` base; match your resource's TS
   interface in `shared-types/index.ts` exactly. Do not change the TS file.
5. **Product invariants:** counts DERIVED server-side; salary never ranks/filters;
   low-confidence postings excluded from Insights.
6. **RLS exclusion:** `skills_taxonomy` is GLOBAL/unscoped — exclude it from any per-user
   export or account-deletion logic.

## TDD + verification

Write the failing test first, then implement. Every lane ships:
- Behavior tests through real HTTP where applicable
  (`httpx.AsyncClient(transport=ASGITransport(app=create_app()))`), `@requires_db`-guarded
  (`from test_db import requires_db`, take `migrated_db: None`, monkeypatch
  `settings.service_jwt_secret` before `mint(...)` — copy the pattern from
  `tests/test_run_api.py`).
- **A cross-tenant test** wherever your lane reads or deletes tenant data: a second user
  (different `sub`) never sees or is affected by the first's rows.
- Green before you call done:
  `cd apps/api && uv run pytest -q && uv run mypy . && uv run ruff check && uv run ruff format --check`
  and, for web-touching lanes, `pnpm -C apps/web lint && pnpm -C apps/web typecheck && pnpm -C apps/web test`.

## Frontend wiring (lanes that own a view)

Your brief says whether you own a web slice. If so: add your page under
`apps/web/src/app/(app)/<x>/`, your components under `apps/web/src/components/<x>/`, your BFF
route under `apps/web/src/app/api/<x>/route.ts`, and your data provider `lib/api/<x>.ts`
(call `await bffFetch(...)` — the shared minter already exists). Use the frozen
`@specula/shared-types` types; do not change them.

## Lane self-reporting (how the integrator sees you)

Your session is opaque to the integrator. Externalize state to files in your worktree:
- **`.lane-status.md`** (live): current phase · blocked? · waiting-on? · shared surfaces you
  had to touch · open questions. Update it whenever your state changes.
- **`.lane-report.md`** (on completion): what you built · test results · any inter-lane
  dependency or shared-surface amendment you hit · anything the integrator must reconcile.

These are per-worktree files (never a single shared status page — that conflicts on every
merge).

## Done = commit on your branch, push, report

When green: commit on `m5-<lane>`, push the branch (CI runs the full suite — the merge gate
is **branch-CI-green**, not laptop-green), write `.lane-report.md`. **Do NOT merge to
`main`** — the integrator seat reviews, runs the full suite on the merge result, and
integrates in order: **NET → OBS → DATA → DASH → LOAD**.
