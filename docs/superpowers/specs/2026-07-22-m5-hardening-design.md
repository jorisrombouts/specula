# Specula M5 (Hardening) — Design & Parallel Fan-out Plan

Date: 2026-07-22 · Status: **draft, awaiting review** · Prev: M0–M4 shipped (`docs/M4-STATUS.md`)

## Context

M0–M4 are shipped and live-proven: the full pipeline (discover → approve → enrich →
crawl → extract → embed → dedup → salary-blind score → write) runs **inline on a manual
trigger**. M5 is the stated next milestone (spec §18, `CLAUDE.md`): harden what exists
before the automation/deploy milestone (scheduler/worker/host) and the M6 polish pass.

**M5 scope (spec §15–16, DoD §19):** observability (structured logs/traces/errors + run &
cost dashboards), rate limits (on-demand gate), scraping politeness (robots.txt + per-host
limits + provenance), export/delete (data export + account-deletion cascade), E2E + load
test, cost controls (OpenAI budget caps).

**Scope boundary — deliberately excluded from M5:** the DoD §19 lines "CI deploys web→Vercel
and api→container host with migrations; post-deploy smoke" and "a scheduled weekly run …
execute the full pipeline" belong to the **deferred automation/hosting milestone** (host
decision still open — Appendix A #3–#6). M5 is the **host-independent hardening subset**.
OBS delivers the observability *instrumentation + config hooks*; wiring a live Sentry DSN /
OTel collector is infra and defers with hosting.

## Milestone sequence (agreed)

**M5 Hardening (this doc) → M6 Polish & launch → Automation/deploy milestone.** The
automation milestone is gated on open decisions #3 Arq vs Celery, #4 Fly.io vs Railway/
Render, #5 run-cadence staggering (Appendix A) — surfaced here so they can be decided in
parallel, but not built in M5.

## Findings that shaped the design (verified against code)

1. **Cost instrumentation is greenfield** — no `logging`, OpenTelemetry, Sentry, or token/
   `.usage` capture exists anywhere in `apps/api`. OBS builds from zero.
2. **The dominant OpenAI spend has no `Run` to attach to.** Only *discovery* creates a
   `Run` (`services/run.py` → `create_run`). *Company ingest* — enrich + per-posting
   extract + embed + score, the bulk of the cost — runs via `services/run.py`
   `trigger_company_ingest` and creates **no `Run` row**. ⇒ cost tracking must be a
   per-call **ledger table**, not columns on `runs` (rollup columns on `runs` are optional
   convenience only).
3. **Coupling hubs that force serialization** (one lane / one PR must own each):
   `packages/shared-types/src/index.ts` (single file, ~40 web importers), the single
   **Alembic chain** (`apps/api/alembic/versions/`), `routers/__init__.py`,
   `services/run.py`, `config.py`, and the web registries `apps/web/src/lib/nav.ts` and
   `lib/api/bff.ts`.
4. **Decoupled seams that are parallel-safe:** per-domain vertical slices
   (router+service+schema on API; page+lib+components on web), the pipeline DI seam
   (`pipeline/deps.py::PipelineDeps`, Protocols in `http.py`/`openai_client.py`), and new
   ATS adapters. This is why fan-out works.
5. **RLS/cascade facts for export/delete** (from the M2 RLS migration): every tenant
   table's `user_id` FK is `ondelete="CASCADE"`, so account deletion is a single
   `DELETE FROM users WHERE id=:uid`. **`skills_taxonomy` is global/unscoped** (no
   `user_id`, not in the per-user RLS set) → it must be **excluded from both export and
   delete**. Any new per-user table (the cost ledger) must get the same RLS treatment.

## Architecture: one serialized foundation, then five parallel lanes

This mirrors how M2 was built (`docs/superpowers/specs/m2-fanout-playbook.md` + per-lane
briefs). **All hub edits land once, on `main`, in the foundation lane. Every parallel lane
then owns a disjoint file set and never touches a hub.**

### Foundation lane (serialized — lands on `main` first, before any lane branches)

- **Migration (one new Alembic revision; `down_revision` = current head — verify at build
  time):**
  - New **`llm_costs`** table: `id, user_id (FK users ondelete CASCADE), run_id (nullable),
    company_id (nullable), stage, model, prompt_tokens, completion_tokens, embed_tokens,
    cost_usd numeric, created_at`. **Add it to the per-user RLS set** (ENABLE + FORCE ROW
    LEVEL SECURITY + `tenant_isolation` policy) exactly like the M2 tables — omitting this
    is a silent tenancy hole.
  - New model `db/models/llm_cost.py` + export from `db/models/__init__.py`.
  - Optional convenience: rollup columns `runs.cost_usd`, `runs.duration_ms`.
  - **`companies.opt_out` (bool)** column for the per-company removal path (§15) — folded in
    here so no lane needs a second migration.
- **Config (`config.py`):** `openai_run_budget_usd`, `openai_daily_budget_usd`;
  `run_rate_limit_per_hour` / `run_cooldown_s`; `log_level`, `sentry_dsn: str | None`,
  `otel_enabled`; a shared model→price map (so OBS's cost math and DASH's display agree).
- **Contract (`packages/shared-types/src/index.ts`, single edit):** extend `Run` with
  optional `cost`; add `LlmCost`, `DashboardSummary`/`CostPoint`, `ExportBundle`,
  `RateLimitError`.
- **Registries (pre-register so lanes only *edit* their own stub):** create empty
  `routers/dashboard.py` and `routers/account.py` stubs + register both in
  `routers/__init__.py`; add `dashboard` + `settings` entries (and `IconName` members) to
  `apps/web/src/lib/nav.ts`.

**Rule:** exactly one Alembic revision and one `index.ts` edit for the whole milestone. Any
unforeseen mid-flight need becomes a tiny **single-file serialized amendment PR** (the
migration *or* `index.ts`), fast-merged, then lanes rebase — never a second live Alembic
revision.

### The five parallel lanes (each owns a disjoint file set)

| Lane | Purpose | Owns (exclusive) | Foundation dep |
|---|---|---|---|
| **OBS** *(L)* | structured JSON logging (request/user/run/stage), error/trace hooks, capture OpenAI `.usage` → write `llm_costs`, enforce per-run + daily budget guard | NEW `observability.py`; `main.py`; `pipeline/openai_client.py` (metering decorator); `pipeline/deps.py`; `services/run.py` (lifecycle + ingest cost + budget guard); stage logging in `pipeline/{discovery,enrich,extract,score,dedup,embeddings,source}.py` | ledger table, config budget/obs keys |
| **DASH** *(M)* | run & cost dashboard, read-only | `routers/dashboard.py` (fills the stub); NEW `services/dashboard.py` (queries under RLS, never edits `run.py`); NEW `schemas/dashboard.py`; NEW web `app/(app)/dashboard/`, `components/dashboard/`, `app/api/dashboard/route.ts`, `lib/api/dashboard.ts` | ledger read shape, dashboard types, nav entry, router stub. *Soft dep on OBS: develop against seeded ledger rows* |
| **NET** *(M)* | on-demand rate-limit gate + scraping-politeness hardening | `pipeline/http.py` (robots/per-host delay/backoff); `pipeline/fetch.py` (provenance); NEW `ratelimit.py` (`rate_limit_guard` dependency); `routers/run.py` + `routers/approval.py` (apply gate) | rate-limit/politeness config keys |
| **DATA** *(M)* | GDPR export + account-deletion cascade + per-company opt-out endpoint | `routers/account.py` (fills stub): `GET /account/export`, `DELETE /account`; NEW `services/account.py` (export under `tenant_session`, delete = `DELETE FROM users`, **excludes `skills_taxonomy`**, includes `llm_costs`); NEW `schemas/account.py`; opt-out endpoint on `routers/company.py`; NEW web `app/(app)/settings/`, `components/settings/`, `app/api/account/*`, `lib/api/account.ts` | `ExportBundle` types, nav entry, router stub, `companies.opt_out` column |
| **LOAD** *(S–M, merges last)* | load-test harness + expanded E2E | NEW top-level `load/` dir (k6/locust); NEW spec files under `apps/web/e2e/authed/` (new files only, inside existing Playwright globs — never touch `playwright.config.ts`) | the merged features it exercises |

### Two files that look shared but aren't (call out in briefs)

- **`services/run.py` (OBS) vs `routers/run.py` (NET)** — different files; name the owner
  explicitly per lane.
- **`pipeline/deps.py` (OBS) ↔ `PoliteFetcher` in `http.py` (NET)** — soft coupling: OBS's
  `deps.py` constructs `PoliteFetcher(settings)`. **NET keeps that constructor signature
  stable** (add tunables via `Settings`, not positional args). Merge NET before OBS.

## Merge / integration order

Foundation → `main` first. Checkpoint: `just lint typecheck test`, then `just migrate` up
**and down** to prove the revision + RLS policy reverse cleanly. Branch all five lanes off
post-foundation `main`. Concurrency: OBS, NET, DATA run fully concurrently; DASH concurrent
(builds against seeded ledger rows); LOAD written concurrently but asserts on merged
features.

**CI-parity merge gate (the load-bearing rule):** gate each merge on **branch-CI-green**
(push the lane branch, let CI run the *full* suite in the real environment), not
laptop-green — then run the CI-equivalent full suite **on the merge result** too, because a
branch can be individually green yet break when integrated. Connect tests as the
least-privilege `specula_app` role so the RLS isolation they assert actually fails-closed (a
superuser/bootstrap role silently bypasses `FORCE ROW LEVEL SECURITY` — this is why the M2
playbook mandates the non-superuser role).

Recommended merge sequence (branch-CI-green + full suite on the merge result between each;
`just e2e` included where noted):

1. **NET** — smallest cross-surface; merge first so OBS rebases onto the final
   `PoliteFetcher`.
2. **OBS** — largest; establishes ledger population + logging.
3. **DATA** — isolated slice; after OBS so `llm_costs` is populated and exercised by
   export/cascade. `just e2e`.
4. **DASH** — after OBS so cost data is real. `just e2e`.
5. **LOAD** — last; its E2E exercises DASH/DATA/NET. Final gate: `just test` + `just e2e` +
   a load run.

## Definition-of-Done mapping (§19)

| DoD / M5 item | Lane |
|---|---|
| data export + account deletion (cascade) | DATA |
| observability (logs/traces/errors) | OBS |
| + run & cost dashboards | DASH |
| cost controls / OpenAI budget caps | OBS (budget guard) |
| rate limits / on-demand gate | NET |
| robots.txt + rate limits; `source_url`+`content_hash` provenance | NET |
| per-company removal path | DATA (endpoint) + foundation (`opt_out` column) |
| E2E + load test | LOAD |
| Auth + account bootstrap | already shipped — no lane |
| CI deploy + scheduled weekly run | **deferred to automation/hosting milestone** |

## How we develop in parallel (the skills)

**Driver skill: `parallel-worktree-development`.** This is the orchestrator for exactly
this shape (serial foundation → concurrent lanes → serial integrator seat); it composes the
component skills below. It formalizes the ad-hoc fan-out M2 already used. Its three phases
map onto this design:

- **Phase 0 — Decompose + declare shared surfaces** *(this doc)*. The shared surfaces are
  the coupling hubs (§ foundation lane). Two classes matter: **files every lane would touch**
  (the migration chain, `shared-types/index.ts`, `routers/__init__.py`, `nav.ts`) — pulled
  into the foundation; and the dangerous **behavioral contracts** — chiefly the **OBS→DASH
  cost-ledger contract** (DASH's tests read a shape OBS writes; nothing flags a mismatch at
  merge). The foundation freezes the ledger schema + model→price map so this contract can't
  drift. Scope rules are **binary**: OBS/NET/DATA are backend-plus-their-own-web-slice;
  LOAD is the only lane that adds cross-cutting E2E; no lane edits another's files.
- **Phase 1 — Foundation lane (serial)**, via `subagent-driven-development`. Delivers the
  hub edits **and a copy-me template**: the existing M2 `targeting`/`insights` vertical
  (`schemas/` + `services/` + `routers/` + `tests/` + web `lib/api/` + `components/`) is the
  worked example DASH and DATA clone. Merge foundation to `main` before any lane branches.
- **Phase 2 — Fan-out lanes**, via `using-git-worktrees`: one worktree per lane under
  `.worktrees/m5-<lane>` on branch `m5-<lane>`, each with its **own isolated DB**
  (`specula_wt_<lane>`, migrated+seeded) and connecting as the **non-superuser `specula_app`
  role** (see gate note below). Each lane gets a `m5-<lane>-brief.md` + the shared
  `m5-fanout-playbook.md`, runs its own TDD→self-review→commit cycle, and **self-reports** to
  `.worktrees/m5-<lane>/.lane-status.md` (live) + `.lane-report.md` (done) so the integrator
  sees blocked/waiting lanes without watching each session. Lanes do **not** merge to `main`.
- **Phase 3 — Integrator seat (serial)**, via `requesting-code-review` +
  `finishing-a-development-branch`. One coordinator merges lanes in the order below through
  the CI-parity gate, then tears each lane down.

`writing-plans` produces the Phase-0 artifacts (`m5-fanout-playbook.md` + per-lane briefs).

## Testing & verification

- Per lane: TDD to green — API `uv run pytest -q && uv run mypy . && uv run ruff check &&
  uv run ruff format --check`; web `pnpm lint typecheck test build`.
- **Cross-tenant tests are mandatory** for DATA (delete user A leaves user B intact; A's
  rows gone from every per-user table incl. `llm_costs`) and for the new ledger reads (DASH
  never sees another tenant's costs).
- Foundation: prove `just migrate` up **and** down (RLS policy reverses).
- End of milestone: full `just test` + `just e2e` + a `load/` run + a manual `RUNNING-LIVE`
  smoke to confirm cost ledger rows appear and budget guard trips.

## Risks & mitigations

1. **Cost plumbing shared OBS(writer)/DASH(reader)** → foundation freezes ledger schema,
   units, and the model→price map before branching; DASH tests against seeded rows and
   never edits `run.py`.
2. **`deps.py`↔`PoliteFetcher` signature** → NET keeps the constructor stable; merge NET
   before OBS.
3. **Export/delete tenancy** → export under `tenant_session` (RLS auto-scopes); exclude
   global `skills_taxonomy`; verify cascade with a cross-tenant test; include `llm_costs`.
4. **Registry conflicts** (`nav.ts`, `routers/__init__.py`) → foundation pre-registers both
   dashboard+settings; lanes edit only their own stub.
5. **Rate-limit backing store** → no Redis this milestone (inline execution). NET uses an
   in-process limiter or a `runs.created_at` cooldown check (no new table). A durable,
   multi-instance limiter needs Redis → deferred with hosting.
6. **Mid-flight schema/contract need** → up-front column audit folds cost ledger,
   `companies.opt_out`, and run rollups into the one migration; surprises become a
   single-file amendment PR, then rebase.

## Open decisions (resolved with defaults — change before branching if desired)

- **Per-company opt-out:** column in foundation migration; endpoint owned by DATA. *(Default
  accepted.)*
- **Rate-limit backing:** in-process / `runs.created_at` cooldown, no Redis. *(Default
  accepted.)*
- **Sentry/OTel:** OBS ships instrumentation + config hooks only; live DSN/collector defers
  with hosting. *(Default accepted.)*
