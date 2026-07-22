# M5 Lane NET — Rate-limit gate + scraping-politeness hardening

Read `m5-fanout-playbook.md` first. Branch `m5-net`, DB `specula_wt_net`. Size: **M**. **Merges first.**

## Purpose
An on-demand rate-limit gate on user-triggered runs/ingests, and a hardening pass on scraping
politeness (robots.txt, per-host delay/backoff, provenance).

## Files you own (touch ONLY these)
- Create `apps/api/specula_api/ratelimit.py` — a reusable `rate_limit_guard` FastAPI
  dependency enforcing `settings.run_rate_limit_per_hour` + `settings.run_cooldown_s`.
  **No Redis this milestone** (inline execution): back it with an in-process limiter or a
  `runs.created_at`/last-action cooldown query. On breach, raise HTTP 429 whose body matches
  the frozen `RateLimitError` TS shape (`{ error: "rate_limited", retryAfterS: <int> }`). Note
  in `.lane-report.md` that a durable multi-instance limiter needs Redis (deferred w/ hosting).
- `apps/api/specula_api/routers/run.py` — apply `Depends(rate_limit_guard)` to `POST /runs`.
- `apps/api/specula_api/routers/approval.py` — apply the gate to the approve→ingest trigger.
- `apps/api/specula_api/pipeline/http.py` — harden `PoliteFetcher`: respect robots.txt,
  per-host delay (`crawl_per_domain_delay_ms`), back off on 429/5xx, descriptive UA
  (`crawl_user_agent`). **Keep the `PoliteFetcher(settings)` constructor signature stable**
  (OBS's `deps.py` constructs it — add tunables via `Settings`, not positional args).
- `apps/api/specula_api/pipeline/fetch.py` — ensure `source_url` + `content_hash` provenance
  is stored for every posting (spec §15).

## Tests
- Gate: exceeding `run_rate_limit_per_hour` within the window → 429 with the `RateLimitError`
  body; a request inside the cooldown → 429; a request after cooldown → allowed.
- Politeness: a `robots.txt` disallow is respected (fetch skipped); a 429 triggers backoff;
  per-host delay is applied (assert via a fake clock/fetcher, no real network).
- Provenance: an ingested posting has non-null `source_url` + `content_hash`.

## Out of scope (binary)
No cost/logging (OBS — do not edit `services/run.py`). No dashboard (DASH). No per-company
opt-out endpoint (DATA owns `routers/company.py`). No `config.py`/migration/`shared-types` edits.
