# M5 (Hardening) — Status

**Shipped.** M5 hardened the M0–M4 pipeline: observability + cost accounting, rate limits,
scraping politeness, GDPR export/delete, and a load/E2E harness. Built as a **parallel
worktree fan-out** — a serial foundation on `main`, then five concurrent lanes, integrated
one at a time through a review + CI gate.

Design: `docs/superpowers/specs/2026-07-22-m5-hardening-design.md` ·
Foundation plan: `docs/superpowers/plans/2026-07-22-m5-foundation.md` ·
Fan-out playbook + per-lane briefs: `docs/superpowers/specs/m5-*.md`.

## What shipped

| Lane | Delivered | Key files |
|---|---|---|
| **Foundation** | `llm_costs` cost-ledger (RLS-forced) + `LlmCost`; `companies.opt_out`; `runs.cost_usd`/`duration_ms`; one Alembic revision; config + `OPENAI_PRICING`; frozen `shared-types` contract; dashboard/account router + nav stubs | `db/models/llm_cost.py`, `alembic/versions/5f2f2fb3a1af_*.py`, `config.py`, `packages/shared-types/src/index.ts` |
| **NET** | On-demand rate-limit gate (per-user cooldown + sliding 1h window; `RateLimitError` 429) on `POST /runs` + approve→ingest. Scraping politeness/provenance confirmed already shipped in M3. | `ratelimit.py`, `routers/{run,approval}.py` |
| **OBS** | Structured JSON logging + request-id middleware + Sentry/OTel init hooks; metering OpenAI client capturing **real `.usage`** (estimate fallback for recorded mode) → `LlmCost` rows + `runs.cost_usd` rollup; per-run/per-day budget guard that halts. | `observability.py`, `pipeline/openai_client.py`, `services/run.py` |
| **DATA** | GDPR `GET /account/export` (RLS-scoped `ExportBundle`, excludes `skills_taxonomy` + embedding vecs, includes `llm_costs`); `DELETE /account` FK cascade (caller-scoped); per-company opt-out, **enforced in ingest**. Web settings slice. | `routers/account.py`, `services/account.py`, `schemas/account.py`, web `settings/` |
| **DASH** | Read-only run & cost dashboard (spend per stage/day/run + run status); sums the **ledger** (not `runs.cost_usd`, since ingest creates no Run); counts derived server-side; tenant-scoped. | `routers/dashboard.py`, `services/dashboard.py`, web `dashboard/` |
| **LOAD** | k6 load harness (`load/`, manual) + activated Playwright E2E for the M5 flows (dashboard, export, rate-limit-429). | `load/`, `apps/web/e2e/authed/*.spec.ts` |

Every lane was reviewed (spec + tenancy + tests) and gated on branch/CI green before merge.
The `dashboard`/`settings` sidebar nav was deferred during the fan-out (linking to
not-yet-existent routes broke the visual harness's `networkidle` wait) and re-added at the
end once the pages existed, with regenerated Linux baselines.

## Follow-ups (M6 / backlog)

**Cost accounting (OBS):**
- Unknown model → `$0` cost — `compute_cost_usd` bills any model absent from `OPENAI_PRICING`
  as free. Log a warning so an unlisted `openai_*_model` doesn't silently zero cost tracking.
- Stage attribution: `enrich` is metered as stage `extract`; no `score` row (scoring cost
  lands under `embed`/`rationale`). No cost dropped — DASH's by-stage reflects this grouping.
- Budget-aborted ingest has no persisted signal (partial postings remain; DASH/UX can't show
  "cost-capped").
- `rationale()`'s `chat.completions.create` usage-capture path is untested (structurally
  identical to the tested `.parse` path).
- **Concurrency caveat:** the `last_usage` side-channel is safe only because pipeline calls
  are strictly sequential today. If stages are ever parallelized (`asyncio.gather` over
  postings sharing one client), interleaved calls could corrupt `last_usage`. Add a docstring
  caveat / revisit before parallelizing.

**Export / delete (DATA):**
- `ExportBundle` (9 frozen keys) omits `approvals`/`posting_state`/`user_settings` — which
  hold user-authored data (dismiss notes, feedback, decisions, UI tweaks). They cascade on
  delete but aren't in the export. Decide whether a "complete" GDPR export should include
  them (a `shared-types` contract change).
- `test_export_is_tenant_disjoint` only checks `companies` are disjoint — broaden to
  postings/scores/llmCosts for parity with the delete-cascade test.

**Dashboard (DASH):**
- In-Python aggregation (no SQL `SUM`/`GROUP BY`, no `LIMIT` before slicing `recentRuns`).
  Fine at current scale; revisit if a tenant's row counts grow large.

**BFF + rate-limit UX (the two are linked): SHIPPED.**
- **BFF error-propagation gap — fixed.** `bffFetchRaw` returns the raw upstream `Response`
  without throwing, and the route handlers (`api/runs`, `runs/rescore`, `runs/refresh`,
  `runs/[id]`, `approvals/[id]/decision`) forward FastAPI's real status + body instead of
  collapsing to an opaque 500. `bffFetch` keeps its throw-on-non-2xx default for the many
  routes that want it.
- **Rate-limit UI surfacing — fixed.** A 429 is parsed into `Rate-limited — try again in
  {retryAfterS}s.` (`lib/api/runs.ts:triggerError`, `lib/api/approvals.ts`) and rendered as a
  warn-styled `role="alert"` status line — `HeaderRefresh` for the run triggers, the queue
  header for approvals.
- Verified end-to-end against the real limiter (unstubbed): trigger #1 → 201, trigger #2 →
  429 `{"error":"rate_limited","retryAfterS":57}` propagated through the BFF route to the
  browser, rendering "Rate-limited — try again in 57s.".
- `ratelimit.spec.ts` now covers **both** halves: the original test asserts FastAPI's 429
  contract over the network; a second test drives the button and asserts the alert the user
  actually sees.

**Foundation minors:**
- `test_m5_migration`'s fail-closed RLS test is weak (asserts zero rows on an empty table);
  the real guarantee is carried by the cross-tenant test. Strengthen if touched.
- `dashboard`/`settings` sidebar icons use stand-in glyphs — final icons are M6 polish.

## Deferred milestones (unchanged from the design)
- **Automation / deploy:** weekly scheduler, Arq worker + Upstash Redis + always-on host,
  SSE `/runs/stream`, CI deploy (web→Vercel, api→container host). Gated on open decisions
  (Arq vs Celery; Fly.io vs Railway/Render). *The `services/run.py` `else` branches are the
  pre-built enqueue seam.*
- **M6 — Polish & launch:** onboarding, empty/loading states, perf budget, security review,
  keyboard-nav/a11y — plus the remaining follow-ups above (the BFF + rate-limit UX pair is
  done).

## Operational note
During the LOAD-spec fix, a test `POST /runs` hit a **live-mode `uvicorn` (real OpenAI key,
port 8000, started from the main worktree)** before it was known to be live, triggering a
real discovery run costing **~$0.155** (run `2b1113f1`). That server was still running at
M5 completion — stop it if not needed (it also blocks local e2e via a port conflict).
