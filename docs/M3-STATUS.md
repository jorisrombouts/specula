# M3 — Manual end-to-end pipeline · STATUS: ✅ COMPLETE (merged PR #2, `83e4be5`)

**What shipped:** the full ingestion + scoring pipeline, **manually triggered** (scheduler/worker/
hosting deliberately deferred — see below). Clicking "Refresh now" (or a run trigger) drives:

`discover (OpenAI web-search) → approval queue → approve → enrich → crawl ATS/careers → extract
(LLM structured output) → embed → dedup → salary-blind scoring + rationale → write → the Jobs/
Insights views render real, scored data.`

- **Execution is inline** (FastAPI `BackgroundTask` / a `tenant_session`), so **no Redis / Arq /
  worker / always-on host** this milestone. Real OpenAI + httpx sit behind a `PipelineDeps` seam;
  tests run on recorded fixtures ($0, deterministic); an env-gated live smoke (`RUN_LIVE_SMOKE=1`)
  is the "prove the product" gate + the source of committed fixtures.
- **Frontend:** "Refresh now" wired (`POST /api/runs` + poll `/api/runs/latest`); sidebar shows
  "synced Nd ago · N new", and goes **amber + "N issues"** when a completed run reports errors.
  Runtime-verified in a real headless browser (before/during/after).
- **Docs:** design spec reconciled with `CLAUDE.md` (removed billing/Stripe/plan-tiers + object
  storage + Next 15 + magic-link; low-confidence threshold unified to 50); manual-trigger pivot
  recorded in the spec + CLAUDE.md.
- **CI:** api + web green (backend 208 tests + live-smoke skeleton; web unit + E2E against the real
  recorded pipeline; visual compare with a **reseed between E2E and visual** so baselines are
  deterministic).

**Two latent bugs found + fixed en route:**
1. FastAPI 0.138 runs background tasks *before* the request-session commit → the run/company row
   wasn't durable when the task queried it. Fixed with an explicit commit-before-schedule in the
   routers.
2. `db/session.py` registered asyncpg's native pgvector codec, which double-processed vectors
   against SQLAlchemy's `Vector` type → would have broken **all** embedding persistence in prod.
   Removed; surfaced only once scoring became the first path to flush real vectors.

**Deferred to a later "automation" milestone (documented, not built):** the weekly scheduler
(per-user, staggered) · Arq worker + Upstash Redis + always-on host (hosting decision still open —
GitHub-Actions-cron vs. paid container, under separate evaluation) · on-demand rate-limit gate ·
Playwright/JS-rendered source adapter · SSE `/runs/stream` · `title_vec` cosine dedup clustering ·
feedback-signal weight nudging.

**Known follow-ups (non-blocking):**
- The visual-harness clock pin only reaches the browser, not SSR, so the sidebar's "Nd ago"
  reflects the CI run date; the day drift stays within the pixel threshold (tolerated), but a
  truly deterministic value would need a server-side clock injection.
- Favicon `<img>`s in approvals/companies render as alt-text URLs in the visual baselines (the
  suite doesn't wait for external images) — pre-existing, cosmetic.
- Live discovery for the demo user hits `FixtureMissing` per query in recorded mode (tallied into
  `stats.errors`) — expected for the review harness; real fixtures come from the live smoke.
