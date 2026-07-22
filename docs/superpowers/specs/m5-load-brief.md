# M5 Lane LOAD — Load-test harness + expanded E2E

Read `m5-fanout-playbook.md` first. Branch `m5-load`, DB `specula_wt_load`. Size: **S–M**.
**Merges LAST** — its assertions exercise NET/OBS/DATA/DASH, which must already be on `main`.

## Purpose
A load-test harness for the API, plus Playwright E2E covering the new M5 flows.

## Files you own (touch ONLY these — new files only)
- Create a top-level `load/` dir: a k6 (preferred, single binary) or locust script that
  drives the authed API — e.g. ramps concurrent `GET /jobs` + `GET /dashboard` and a metered
  ingest — reporting p95 latency and error rate. Include a short `load/README.md` (how to run,
  what thresholds mean). Disjoint from all app code.
- Add NEW spec files under `apps/web/e2e/authed/` — e.g. `dashboard.spec.ts`,
  `export.spec.ts`, `ratelimit.spec.ts`. **New files only**; keep them inside the existing
  Playwright project globs so you never touch `playwright.config.ts`.
- (Optional) new API test files under `apps/api/tests/` for cross-lane integration.

## Tests / deliverables
- E2E: dashboard renders spend; export downloads a bundle; a rate-limited trigger surfaces
  the 429 to the user. Run: `just e2e`.
- Load: a documented run against the local stack with a recorded p95 + error-rate baseline in
  `load/README.md`. Flag (don't silently cap) any coverage you couldn't drive.

## Because you merge last
Rebase onto the integrated `main` after DASH lands, then write assertions against the real
merged behavior. If a feature you target isn't merged yet, stub the spec `test.skip` with a
note in `.lane-status.md` rather than asserting against a stub.

## Out of scope (binary)
No app/product code — you only add tests + the load harness. No `shared-types`/migration/
`config.py`/registry edits.
