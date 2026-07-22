# Specula

Personal, multi-tenant "role ledger": job discovery + salary-blind match scoring, with an
editorial-instrument UI. Built in phases (M0–M6). **M0–M5 are done** — the full pipeline
(discover → approve → crawl → extract → score) runs on a manual, inline trigger and is
live-proven against real ATS boards and OpenAI; M5 hardened it (observability + OpenAI cost
ledger + budget guard, rate limits, GDPR export/delete, run & cost dashboard, load/E2E).
**M6 (Polish & launch)** is the current focus. See `docs/M5-STATUS.md` for what shipped and
`CLAUDE.md` for the build rules.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python toolchain; manages Python 3.12+)
- [just](https://github.com/casey/just) (`brew install just`)
- Node 20 via [corepack](https://nodejs.org/api/corepack.html) → pnpm (`corepack enable`)
- Docker (with Compose v2) for local Postgres + pgvector

## Quickstart

```bash
just setup     # uv sync + pnpm install + pre-commit install
just up        # start Postgres + pgvector
just migrate   # apply DB migrations
just seed      # seed the demo tenant + representative data
just dev-api   # FastAPI on http://localhost:8000  (GET /health -> {"status":"ok"})
just dev-web   # Next.js on http://localhost:3000
```

## Layout

```
apps/api/          FastAPI service (uv · ruff · mypy --strict · pytest · SQLAlchemy 2.0 · Alembic · pgvector)
apps/web/          Next.js 16 app (TS strict · Tailwind · ESLint + Prettier)
packages/shared-types/   Types shared between web and api
docs/              Design specs (source of truth) + milestone status + SKILL-MATCHING (scoring thresholds)
db/                SQL helpers for local Postgres setup
prototype/         Pixel-faithful UI prototype — serve over HTTP to view (cd prototype && python3 -m http.server), not file://
docker-compose.yml   Local Postgres + pgvector
justfile           One entrypoint into both apps
```

## Commands

| Command | What it does |
|---|---|
| `just setup` | Install all deps + git hooks |
| `just up` / `just down` | Start/stop local infra (Postgres + pgvector) |
| `just migrate` / `just seed` | Apply migrations, then seed the demo tenant + representative data |
| `just dev-api` / `just dev-web` | Run an app locally (`just dev-web-noauth` bypasses Google sign-in) |
| `just lint` / `just fmt` / `just typecheck` / `just test` | Quality gates across both apps |
| `just e2e` / `just visual` | Web Playwright E2E / visual-regression suites |
| `just prove-live` / `just live-discover` / `just live-ingest <domain>` | Run the pipeline against real OpenAI + ATS traffic — **costs credits**, see `docs/RUNNING-LIVE.md` |

Full list: `just --list`.
