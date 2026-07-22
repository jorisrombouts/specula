# M5 Lane OBS — Observability + cost instrumentation + budget guard

Read `m5-fanout-playbook.md` first. Branch `m5-obs`, DB `specula_wt_obs`. Size: **L** (largest lane).

## Purpose
Structured logging + error/trace hooks across the API and pipeline; capture OpenAI token
usage → write `llm_costs` rows; enforce per-run and per-day OpenAI budget caps.

## Files you own (touch ONLY these)
- Create `apps/api/specula_api/observability.py` — logging config (structured JSON: request
  id, user id, run id, stage), a request-id middleware, and optional Sentry/OTel init gated
  on `settings.sentry_dsn` / `settings.otel_enabled` (init only — no live DSN this milestone).
- `apps/api/specula_api/main.py` — wire the middleware + observability init (no other lane
  touches `main.py`).
- `apps/api/specula_api/pipeline/openai_client.py` — add a `MeteringOpenAIClient` decorator
  (mirror the existing `RecordingOpenAIClient` pattern) that captures `.usage` from every
  call and reports (stage, model, prompt/completion/embed tokens) to a cost sink.
- `apps/api/specula_api/pipeline/deps.py` — wire the metering client + a per-run cost sink
  into `PipelineDeps`. **Keep `PoliteFetcher(settings)` construction unchanged** (NET owns
  its signature).
- `apps/api/specula_api/services/run.py` — this lane's exclusively. Record run lifecycle
  (`started_at`/`finished_at`/`duration_ms`), write `LlmCost` rows and the `runs.cost_usd`
  rollup, and **enforce the budget guard**: abort/mark the run or ingest when accumulated
  spend exceeds `settings.openai_run_budget_usd` (per run) or `openai_daily_budget_usd` (per
  user/day). Remember `trigger_company_ingest` creates NO `Run` — record its cost with
  `run_id=None, company_id=<id>`.
- Stage logging only in `pipeline/{discovery,enrich,extract,score,dedup,embeddings,source}.py`.

## Behavioral contract you must honor (OBS→DASH)
DASH reads what you write. A `LlmCost` row = one OpenAI call: `stage` ∈
{`discovery`,`extract`,`embed`,`score`,`rationale`}, `model` = the model used, token counts
from `.usage`, `cost_usd` computed from `config.OPENAI_PRICING` (USD/1M tokens). The
`runs.cost_usd` rollup = sum of that run's ledger rows. Use `OPENAI_PRICING` for the math so
DASH's display agrees.

## Tests
- Cost capture: a recorded-mode ingest writes `LlmCost` rows with correct stage/model and a
  `cost_usd` matching `OPENAI_PRICING` (use existing recorded fixtures — no live spend).
- Budget guard: a run whose simulated spend exceeds `openai_run_budget_usd` is marked
  errored/aborted and stops making calls.
- Cross-tenant: user B never sees user A's `llm_costs` rows.
- Logging: a request emits a JSON line carrying request/user id (assert shape, not exact text).

## Out of scope (binary)
No dashboard UI (DASH). No rate limiting (NET). No `shared-types` / migration / `config.py`
edits (foundation). Sentry/OTel *live* backends are deferred — ship the init hooks only.
