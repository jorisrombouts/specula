# Refresh jobs (re-crawl tracked companies) — implementation plan

**Goal:** A "Refresh jobs" action on the Jobs page that re-crawls every tracked (approved, non-opted-out) company for **new postings**, extracts + scores them, and re-renders the pool — the missing "tracker" refresh. Re-score stays on the Candidate page.

**Architecture:** Loop the existing, tested `ingest_company` (enrich→fetch→extract→embed→dedup→score) over the user's tracked companies, wrapped in a `Run(kind="refresh")` for observability + rate limiting (mirrors `run_rescore`/`run_discovery`). Frontend generalizes the rescore poll into a `usePolledRun` hook and swaps the Jobs-page button.

**Constraints:** mypy --strict + ruff clean (api); tsc + eslint + prettier clean (web). Daily budget guard already protects the loop (each `ingest_company` re-seeds the daily baseline and aborts cleanly). **Stage only refresh-jobs files — never `git add -A`** (the working tree holds the user's unrelated candidate/targeting staleness edits).

## Tasks

- [ ] **T1 — `refresh_all_jobs`** (`services/run.py`). `async def refresh_all_jobs(session, user_id, deps) -> dict[str,int]`: count the user's postings before; for each `Company` where `user_id` + `not opt_out`, `await ingest_company(session, user_id, company.id, deps)`; count after; return `{"companies": n, "new": after-before}`. TDD: loops over tracked companies, skips opted-out, returns the new-posting delta (stub OpenAI + a fake fetcher that adds a posting).

- [ ] **T2 — `run_refresh` + `trigger_refresh_run`** (`services/run.py`), mirroring `run_rescore`: set running, seed baseline, call `refresh_all_jobs`, stats `{"found":0,"new":new,"closed":0,"low_conf_excluded":0,"errors":0,"scored":0}`, finalize done/error, budget-guarded. Add `"refresh"` to `latest_run`'s excluded kinds (`Run.kind.notin_(["rescore","refresh"])`). TDD: latest_run excludes a refresh run.

- [ ] **T3 — `POST /runs/refresh`** (`routers/run.py`), mirror `start_rescore`: `rate_limit_guard`, `create_run(kind="refresh")`, background `trigger_refresh_run`. TDD (HTTP): 201 kind=refresh, inline completes to done, excluded from `/runs/latest`.

- [ ] **T4 — client + BFF** (`lib/api/runs.ts` + `app/api/runs/refresh/route.ts`): `triggerRefresh()` mirroring `triggerRescore` (429 → "Rate-limited…", else "Refresh failed"); BFF route mirroring `/api/runs/rescore`. TDD in `runs.test.ts`.

- [ ] **T5 — `usePolledRun` hook + buttons** (`lib/use-polled-run.ts`): generalize `useRescore` into `usePolledRun({trigger, describe, onDone?})` returning `{busy,note,error,start}`. Refactor Candidate `RescoreButton` to `usePolledRun({trigger:triggerRescore, describe:r=>"Re-scored N jobs…"})`. New `JobsRefreshButton` = `usePolledRun({trigger:triggerRefresh, describe:r=>`Found ${r.stats.new} new job${…}.`, onDone:()=>router.refresh()})` rendered via `HeaderRefresh` (label "Refresh jobs", busy "Refreshing…"). Delete `use-rescore.ts`, `jobs-rescore-button.tsx`+test. TDD: JobsRefreshButton triggers→polls→"Found N new jobs"→router.refresh; rate-limit alert.

- [ ] **T6 — swap the Jobs button** (`components/jobs/jobs-view.tsx`): render `<JobsRefreshButton/>` instead of `<JobsRescoreButton/>`. Add `/runs/refresh` branch to `mockBffFetch` in `test-fixtures.ts`. Fix `jobs-view.test.tsx` if it referenced the rescore button.

## Verification (acceptance)

- `cd apps/api && uv run pytest -q && uv run mypy .` green; `cd apps/web && pnpm exec vitest run && pnpm exec tsc --noEmit && pnpm lint` green.
- **Headless (live mode)**: Jobs page shows "Refresh jobs"; click → "Refreshing…" → run completes → status shows "Found N new job(s)…"; the run row is `kind=refresh, status=done` in the DB and it actually crawled companies (llm_costs / postings touched). Candidate page still shows "Re-score jobs". Screenshot the Jobs header.
- Merge to `main` (stage only refresh-jobs files), push.
