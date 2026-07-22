# Specula API load harness (k6)

A [k6](https://k6.io) script that drives the authed FastAPI under concurrency and reports
per-endpoint p95 latency + error rate. It authenticates exactly like the Next BFF does — a
short-lived HS256 service JWT (`iss=specula-web`, `aud=specula-api`, `sub=<seeded user>`) in
an `Authorization: Bearer` header — so no browser or Next server is involved.

## Install

```sh
brew install k6         # macOS; see https://k6.io/docs/get-started/installation for others
```

## Run

Point it at a running API (the same one the app talks to) and give it the service-JWT secret
that API validates with:

```sh
# from the repo root
k6 run -e SERVICE_JWT_SECRET=<secret> -e API_URL=http://localhost:8000 load/script.js
```

The secret must match the API's `SERVICE_JWT_SECRET`. In a fan-out worktree that is the value
in `apps/api/.env` (e.g. `dev-fanout-secret`); against the shared dev stack use whatever the
running uvicorn was started with.

### Scenarios

| scenario | when | what it does |
|----------|------|--------------|
| `browse` | always | Ramping VUs on the read path: 75% `GET /jobs`, 25% `GET /dashboard`, with 100–600ms think time. This is the load baseline. |
| `ingest` | only with `-e INGEST=1` | A **metered** `POST /runs` at ~1 trigger / 10s (constant arrival rate). Off by default: it mutates the tenant's latest-run, and once the NET rate-limit lands it is *expected* to `429` past the hourly cap. Point it at an API started with `PIPELINE_MODE=recorded` so the triggered run replays fixtures instead of calling OpenAI. |

### Knobs (all `-e KEY=value`)

| key | default | meaning |
|-----|---------|---------|
| `SERVICE_JWT_SECRET` | — (required) | HMAC secret the API validates the JWT with. |
| `API_URL` | `http://localhost:8000` | API base (the script appends `/api/v1`). |
| `USER_SUB` / `USER_EMAIL` | `demo-user` / `demo@specula.app` | Identity to load as; defaults to the seeded demo tenant so reads return real data. |
| `VUS` | `20` | Peak concurrent virtual users for `browse`. |
| `RAMP` / `HOLD` | `20s` / `40s` | Ramp-up and steady-state durations (plus a fixed 10s ramp-down). |
| `INGEST` | `0` | Set `1` to add the metered ingest scenario. |

## Thresholds — what a pass/fail means

The run **fails** (non-zero exit, red `✗` in the summary) if any of these are crossed. Treat a
crossing as a regression to investigate, not noise:

- `endpoint_errors: rate<0.01` — under 1% *unexpected* responses. A read that isn't `200`, or
  an ingest that is neither `201` (accepted) nor `429` (metered) counts as an error. Expected
  rate-limit `429`s are recorded in `rate_limited_429` and deliberately **not** counted here
  (the built-in `http_req_failed` would miscount them).
- `jobs_latency: p(95)<500` — `GET /jobs` 95th-percentile under 500ms.
- `dashboard_latency: p(95)<500` — `GET /dashboard` 95th-percentile under 500ms.

## Recorded baseline

Local stack — API (`uvicorn`, `PIPELINE_MODE=recorded`) against `specula_wt_load` (seeded demo
tenant: 13 postings), macOS / Apple Silicon, k6 v2.1.0.

**`browse`, 20 VUs, 70s** (`k6 run -e SERVICE_JWT_SECRET=… -e API_URL=http://localhost:8010 load/script.js`):

| metric | value |
|--------|-------|
| requests | 2 468 (~35 req/s) |
| errors (`endpoint_errors`) | **0.00%** (0 / 2 467) |
| `GET /jobs` p95 | **251 ms** (avg 124, med 102, max 824) |
| `GET /dashboard` p95 | **13 ms** (avg 3.7) |

**`ingest` smoke, `INGEST=1`, 5 VUs, 15s:** `POST /runs` → `201`, `ingest_latency` p95 **54 ms**,
`endpoint_errors` 0.00%.

### Coverage flags (not silently capped)

- **`GET /dashboard`** currently returns the DASH pre-merge stub (`{status:not_implemented}`),
  a real `200` — so the read path and its latency are exercised, but not the `DashboardSummary`
  aggregation cost. Re-baseline after DASH merges.
- **Rate-limit `429`s** were not observed: the NET hourly-cap enforcement is not on this branch
  yet (`rate_limited_429 = 0`). Once NET lands, re-run `INGEST=1` past the cap to confirm the
  harness records `429`s as metered rather than errors.
