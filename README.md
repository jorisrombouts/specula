# Specula

Personal "role ledger": job discovery + salary-blind match scoring, with an editorial-instrument UI.
Built in phases (M0–M6). This repository is currently at **Phase 0** — repo scaffold and tooling only.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python toolchain; manages Python 3.12)
- [just](https://github.com/casey/just) (`brew install just`)
- Node 20 via [corepack](https://nodejs.org/api/corepack.html) → pnpm (`corepack enable`)
- Docker (with Compose v2) for local Postgres + pgvector

## Quickstart

```bash
just setup     # uv sync + pnpm install + pre-commit install
just up        # start Postgres + pgvector
just dev-api   # FastAPI on http://localhost:8000  (GET /health -> {"status":"ok"})
just dev-web   # Next.js on http://localhost:3000
```

## Layout

```
apps/api/    FastAPI service (uv · ruff · mypy --strict · pytest)
apps/web/    Next.js 16 app (TS strict · Tailwind · ESLint + Prettier)
docs/        Design specs (source of truth)
prototype/   Pixel-faithful UI prototype — serve over HTTP to view (cd prototype && python3 -m http.server), not file://
docker-compose.yml   Local Postgres + pgvector
justfile     One entrypoint into both apps
```

## Commands

| Command | What it does |
|---|---|
| `just setup` | Install all deps + git hooks |
| `just dev-api` / `just dev-web` | Run an app locally |
| `just lint` / `just fmt` / `just typecheck` / `just test` | Quality gates across both apps |
| `just up` / `just down` | Start/stop local infra |
