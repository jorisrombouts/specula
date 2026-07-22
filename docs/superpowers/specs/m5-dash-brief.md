# M5 Lane DASH — Run & cost dashboard (read-only)

Read `m5-fanout-playbook.md` first. Branch `m5-dash`, DB `specula_wt_dash`. Size: **M**.
Soft-depends on OBS's ledger writes — **build against seeded `llm_costs` rows**, don't wait.

## Purpose
A read-only internal dashboard: LLM spend per run / per day / per stage, plus run status.

## Files you own (touch ONLY these)
- `apps/api/specula_api/routers/dashboard.py` — fill the foundation stub: `GET /dashboard`
  returns `DashboardSummary`.
- Create `apps/api/specula_api/services/dashboard.py` — aggregate `runs` + `llm_costs` **under
  RLS** (both are per-user tables → `Depends(get_session)` auto-scopes; also scope by
  `user_id` in the query). Compute `totalCostUsd`, `runCount`, `costByStage`, `costByDay`
  (`CostPoint[]`), `recentRuns` (`Run[]`). **Counts DERIVED server-side — never stored.**
  **Do NOT edit `services/run.py`** (OBS owns it).
- Create `apps/api/specula_api/schemas/dashboard.py` — serialize to the frozen
  `DashboardSummary`/`CostPoint`/`CostByStage` camelCase shapes (clone `CamelModel` from
  `schemas/targeting.py`).
- Web slice: `apps/web/src/app/(app)/dashboard/page.tsx` (route already in nav),
  `apps/web/src/components/dashboard/`, `apps/web/src/app/api/dashboard/route.ts`,
  `apps/web/src/lib/api/dashboard.ts` (`await bffFetch(...)`).

## Seed for development
Insert a handful of `llm_costs` rows for the demo user (varied `stage`/`model`/`created_at`)
in your worktree DB so the aggregation + UI can be built and tested before OBS lands. Put
this in a test fixture / local seed helper you own — not in the shared `seed.py`.

## Tests
- Aggregation: given known `llm_costs` rows, `GET /dashboard` returns correct
  `totalCostUsd`, `costByStage`, `costByDay`, `runCount`.
- Cross-tenant: user B's dashboard never includes user A's costs/runs.
- Web: a component test renders the summary from a mocked `DashboardSummary`.

## Out of scope (binary)
No cost *writing* or budget guard (OBS). No rate limiting (NET). No export/delete (DATA). No
`shared-types`/migration/`config.py`/registry edits (foundation).
