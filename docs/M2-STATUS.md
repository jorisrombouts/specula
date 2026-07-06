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
| **candidate** | ⬜ | `m2-candidate` | `specula_wt_candidate` | `specs/m2-candidate-brief.md` | — | Closest clone of targeting (1:1) |
| **tweaks** | ⬜ | `m2-tweaks` | `specula_wt_tweaks` | `specs/m2-tweaks-brief.md` | — | Small; localStorage→server |
| **companies** | ⬜ | `m2-companies` | `specula_wt_companies` | `specs/m2-companies-brief.md` | — | tracking toggle |
| **lenses** | ⬜ | `m2-lenses` | `specula_wt_lenses` | `specs/m2-lenses-brief.md` | `lens_filter`* | Derived counts |
| **jobs-state** | ⬜ | `m2-jobs-state` | `specula_wt_jobs_state` | `specs/m2-jobs-state-brief.md` | `lens_filter`* | Meatiest lane |
| **insights** | ⬜ | `m2-insights` | `specula_wt_insights` | `specs/m2-insights-brief.md` | — | Exclude low-confidence |
| **approvals** | ⬜ | `m2-approvals` | `specula_wt_approvals` | `specs/m2-approvals-brief.md` | — | approve → add company |
| **frontend-wiring** | ⬜ | (last, serial) | — | — | all backend lanes | Shared bffFetch + service-JWT minter; runs after the API contract is frozen |

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
