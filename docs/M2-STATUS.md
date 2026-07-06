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
| **tweaks** | ⬜ | `m2-tweaks` | `specula_wt_tweaks` | `specs/m2-tweaks-brief.md` | — | Small; localStorage→server |
| **companies** | ✅ merged | `m2-companies` | `specula_wt_companies` | `specs/m2-companies-brief.md` | — | open-roles derived; 409 on domain clash. **Established `web/src/lib/api/bff.ts` placeholder** (throws) + wired tracking toggle |
| **lenses** | ✅ merged | `m2-lenses` | `specula_wt_lenses` | `specs/m2-lenses-brief.md` | — | **Owns `services/lens_filter.py`** now on `main`; derived counts clean |
| **jobs-state** | 🟡 | `m2-jobs-state` | `specula_wt_jobs_state` | `specs/m2-jobs-state-brief.md` | ⚠️ `lens_filter` exists on main | On merge: DROP any duplicate `lens_filter.py` it built; use main's `lens_where(lens)->list[ColumnElement]` + `new_predicate()`. Rebase on main first |
| **insights** | ⬜ | `m2-insights` | `specula_wt_insights` | `specs/m2-insights-brief.md` | — | Exclude low-confidence |
| **approvals** | ⬜ | `m2-approvals` | `specula_wt_approvals` | `specs/m2-approvals-brief.md` | — | approve → add company |
| **frontend-wiring** | ⬜ | (last, serial) | — | — | all backend lanes | **Replace `web/src/lib/api/bff.ts` placeholder** with the real service-JWT-minting helper. Then: wire candidate's provider (still on seed) + verify companies' already-wired toggle. Any lane that shipped its own bff.ts placeholder = keep main's at merge |

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
