# M2 Fan-out — Status Board

Single source of truth for the parallel M2 lanes. The **integrator** (this Claude
session on `main`) keeps it current; lanes never edit it. Coordination happens through
git — a lane is "done" when it's committed + green on its branch; the integrator
reviews, merges to `main`, and updates this board.

**Legend:** ⬜ not started · 🟡 in progress · 🟢 green on branch (ready to integrate) ·
✅ merged to `main` · 🔵 blocked

_Last updated: 2026-07-06 — foundation merged; fan-out infra ready; lanes launching._

## Lanes

| Lane | Status | Branch | DB | Brief | Depends on | Notes |
|---|---|---|---|---|---|---|
| **targeting** | ✅ merged | (foundation) | — | — | — | Built in M2a as the copy-me template |
| **candidate** | ✅ merged | `m2-candidate` | `specula_wt_candidate` | `specs/m2-candidate-brief.md` | — | Clean clone; FE deferred to wiring lane. `Candidate.name` lives on `users` — wiring lane composes it |
| **tweaks** | ✅ merged | `m2-tweaks` | `specula_wt_tweaks` | `specs/m2-tweaks-brief.md` | — | server-backed; Literal-union 422 guard; localStorage=cache |
| **companies** | ✅ merged | `m2-companies` | `specula_wt_companies` | `specs/m2-companies-brief.md` | — | open-roles derived; 409 on domain clash. **Established `web/src/lib/api/bff.ts` placeholder** (throws) + wired tracking toggle |
| **lenses** | ✅ merged | `m2-lenses` | `specula_wt_lenses` | `specs/m2-lenses-brief.md` | — | **Owns `services/lens_filter.py`** now on `main`; derived counts clean |
| **jobs-state** | ✅ merged | `m2-jobs-state` | `specula_wt_jobs_state` | `specs/m2-jobs-state-brief.md` | — | Read-model + state PATCH; **reconciled `lens_filter.py`** into one superset (both suites pass) |
| **insights** | ✅ merged | `m2-insights` | `specula_wt_insights` | `specs/m2-insights-brief.md` | — | Aggregates + skills-gap; low-conf (conf<50) excluded everywhere |
| **approvals** | ✅ merged | `m2-approvals` | `specula_wt_approvals` | `specs/m2-approvals-brief.md` | — | queue + decision; approve→company (enrichment M3) |
| **frontend-wiring** | 🟡 parked (branch `m2-frontend-wiring`, ~60%, NOT merged) | `m2-frontend-wiring` | — | `specs/m2-frontend-wiring-brief.md` | all backend lanes | DONE: real `bffFetch` (jose HS256, contract proven), providers→API, BFF routes forward, candidate save, unit tests. OUTSTANDING before merge: (1) **bypass crash** — API-backed app breaks `DEV_AUTH_BYPASS` (`auth()`→null→bffFetch throws); fix = dev-only bypass branch minting for the seeded demo user. (2) **test harness** — Playwright visual+E2E and the web CI job must run the real stack (uvicorn + seeded Postgres + `SERVICE_JWT_SECRET`/`API_URL`; visual global-setup mints `sub=demo-user`). (3) verify E2E+visual+manual smoke → merge. FOLLOW-UP: jobs client lens re-sort keys off hardcoded lens-ids but real lenses are UUIDs (server `?lens=` filtering is correct) — an M1c client redesign. |

\* **`lens_filter` coordination:** `services/lens_filter.py` (`lens_where()`) is shared by
`lenses` and `jobs-state`. Whichever lands first **owns/creates** it; the second
**rebases** on `main` and reuses it. Integrator enforces this at merge time.

## Recommended merge order

Foundation ✅ → independent config lanes (**candidate, tweaks, companies**) →
**lenses** then **jobs-state** (or vice-versa; second rebases) → **insights, approvals**
→ **frontend-wiring** last.

## Integrator log

_(append one line per integration event)_
- 2026-07-06 — board created; M2a foundation merged (`de372e5`); 7 worktrees + DBs live.
- 2026-07-06 — **candidate** merged (`1bbcc8d`). Clean clone of targeting; 30 passed / mypy / ruff / format green; cross-tenant verified. FE correctly deferred. Note: `Candidate.name` (TS) has no `candidate_profiles` column — it's on `users`; the frontend-wiring lane composes name from user + profile.
- 2026-07-06 — **lenses** merged (`a89cb65`, resolved trivial `routers/__init__.py` import conflict). 35 passed on main / mypy / ruff green. **`services/lens_filter.py` now lives on `main`** — interface: `lens_where(lens) -> list[ColumnElement[bool]]` (modes/foreign_hq/scope; default→[]) + `new_predicate()`. ⚠️ jobs-state built independently and may carry its own copy → at its merge, keep main's version, drop the duplicate, and make jobs' pool query use it.
- 2026-07-06 — **companies** merged (`5416e6c`, trivial `routers/__init__.py` conflict). api 40 passed/mypy/ruff + web typecheck/lint/134 tests, verified both sides. Derived open-roles (outerjoin), domain-clash 409. **Introduced `web/src/lib/api/bff.ts` as a throwing placeholder** — reads fall back to seed, writes 501. Frontend-wiring lane replaces it with the real minter; later lanes carrying their own bff.ts keep main's at merge.
- 2026-07-06 — **jobs-state** merged (`9ceb162`). The meatiest lane + the lens_filter reconciliation. Two `lens_filter.py` copies (lenses' on main, jobs' on branch) UNIFIED into one superset: `lens_where(lens|None)` (modes/foreign_hq/scope, strict is_default) + `new_predicate()` (lenses' isNew) + `is_default_lens()` (jobs' loc factor). Integration gate: both test_lenses_api.py + test_jobs_api.py pass together — api 60 passed/mypy/ruff, web typecheck/lint/141 tests. Scoring blend 0.4/0.4/0.2, salary display-only, Rule-6 state.user_id. (Cleared local gitignored playwright-report/.next cruft that was tripping web eslint.)
- 2026-07-06 — **insights** merged. /insights + /skills-gap aggregates; LOW_CONFIDENCE_THRESHOLD=50 excludes untrusted from every aggregate (invariant), salary display-only, derived counts. api 66 passed/mypy/ruff, web 141. **CI fix (`61fc656`): CI now seeds the test DB (mirror db-bootstrap)** so read-model tests (lens counts, insights) have the demo pool — they were failing only in CI since the lenses merge.
- 2026-07-06 — **approvals** merged. Undecided queue (partial index), POST decision (422 on bad value), approve→Company respecting unique(user_id,domain) with name coalesce; enrichment deferred to M3. api 74 passed/mypy/ruff, web 144. FE buttons wired; BFF→FastAPI proxy awaits bffFetch.
- 2026-07-06 — **tweaks** merged — LAST backend lane. Literal-union validated GET/PUT /tweaks, server-backed TweaksProvider (edited-latch fixes in-flight race). **All 8 M2 backend verticals now on main**: api 78 passed/mypy/ruff/format, web typecheck/lint/150 tests. Next & final: **frontend-wiring** lane.
- 2026-07-06 — CI visual-regression fix (`460cdd8`): the tweaks lane's server-backed provider (server-wins reconcile) reverted the localStorage-seeded layout in the M1d-2 cards/ring visual tests → toBeVisible failed in CI (web job). Fixed by pinning the tweak on BOTH inputs (localStorage + intercepted /api/tweaks). **FOLLOW-UP for frontend-wiring lane:** stub GET /api/tweaks returns full defaults and the provider spreads them, so local tweaks currently revert across a reload — that lane makes GET /tweaks return the user's stored prefs (resolves the transitional UX).
- 2026-07-06 — STATUS SYNC: 8/9 M2 lanes merged & green on main. **frontend-wiring parked** on branch `m2-frontend-wiring` (5 commits, ~60%): real bffFetch built + contract-proven; providers/routes/candidate wired; unit tests green. NOT merged — outstanding: bypass-crash fix + full-stack test harness (Playwright + web CI) + verify. On main the app still renders from seed (the fan-out lanes' frontend goes through the throwing bff.ts placeholder → seed fallback / 501). M2 is NOT complete until frontend-wiring merges.
