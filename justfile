set shell := ["bash", "-uc"]

# Install all deps and git hooks
setup:
    cd apps/api && uv sync
    pnpm install
    pre-commit install

# Run the API with reload on :8000
dev-api:
    cd apps/api && uv run uvicorn specula_api.main:app --reload --port 8000

# Run the web app on :3000
# NODE_EXTRA_CA_CERTS lets Node trust a corporate-proxy CA for outbound TLS
# (Auth.js fetches Google's OIDC config at sign-in). Uses your env value if set,
# else ~/.corp-ca.pem (build it: security find-certificate -a -p <keychain> > ~/.corp-ca.pem).
dev-web:
    cd apps/web && NODE_EXTRA_CA_CERTS="${NODE_EXTRA_CA_CERTS:-$HOME/.corp-ca.pem}" pnpm dev

# Same as dev-web but skips the Google sign-in guard so the (app) views render
# without logging in — for local UI work/verification only. DEV_AUTH_BYPASS is
# double-gated in (app)/layout.tsx (dev + this flag) so it can NEVER run in prod.
dev-web-noauth:
    cd apps/web && DEV_AUTH_BYPASS=1 NODE_EXTRA_CA_CERTS="${NODE_EXTRA_CA_CERTS:-$HOME/.corp-ca.pem}" pnpm dev

# Lint both apps
lint:
    cd apps/api && uv run ruff check
    cd apps/web && pnpm lint

# Format both apps
fmt:
    cd apps/api && uv run ruff format
    cd apps/web && pnpm format

# Type-check both apps
typecheck:
    cd apps/api && uv run mypy .
    cd apps/web && pnpm typecheck

# Test both apps (api: pytest, web: vitest)
test:
    cd apps/api && uv run pytest
    cd apps/web && pnpm test

# Browser E2E for the web app (Playwright)
e2e:
    cd apps/web && pnpm test:e2e

# Start local infra (Postgres + pgvector)
up:
    docker compose up -d

# Stop local infra
down:
    docker compose down

# Apply all pending DB migrations (as the specula_app role via DATABASE_URL)
migrate:
    cd apps/api && uv run alembic upgrade head

# Roll back migrations (default one step): just migrate-down  |  just migrate-down base
migrate-down rev="-1":
    cd apps/api && uv run alembic downgrade {{rev}}

# Create a new (empty) migration to hand-edit: just migration "add widget table"
migration name:
    cd apps/api && uv run alembic revision -m "{{name}}"

# Seed the demo user + representative data (idempotent)
seed:
    cd apps/api && uv run python -m specula_api.seed

# Live pipeline harness (demo tenant, dev DB on :55432). Requires OPENAI_API_KEY in the env.
# Always runs PIPELINE_MODE=record so real responses also regenerate the committed fixtures
# in apps/api/tests/fixtures/pipeline — see docs/RUNNING-LIVE.md.

# Real OpenAI web-search discovery run for the demo user; prints the approvals found.
live-discover:
    cd apps/api && PIPELINE_MODE=record uv run python -m specula_api.cli discover

# Approve the demo user's undecided approval matching DOMAIN and ingest it (real
# enrich+crawl+extract+embed+score); prints the resulting job(s). e.g. just live-ingest acme.com
live-ingest domain:
    cd apps/api && PIPELINE_MODE=record uv run python -m specula_api.cli ingest {{domain}}

# End-to-end proof: discover, ingest the first ATS-detected approval (one company only —
# cost guardrail), print its scored jobs.
prove-live:
    cd apps/api && PIPELINE_MODE=record uv run python -m specula_api.cli prove-live

# Create + prepare a database on the shared container. Extensions + the specula_app
# grant need the superuser; migrate/seed then run as the non-superuser specula_app.
db-create db:
    docker compose exec -T postgres psql -U specula -d specula -c "CREATE DATABASE {{db}} OWNER specula" || true
    docker compose exec -T postgres psql -U specula -d {{db}} -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS citext; GRANT CREATE, USAGE ON SCHEMA public TO specula_app;"

# Bring a per-worktree DB fully online: create + migrate + seed. e.g.:
#   just db-bootstrap specula_wt_lenses
db-bootstrap db:
    just db-create {{db}}
    DATABASE_URL="postgresql+asyncpg://specula_app:specula@localhost:55432/{{db}}" just migrate
    DATABASE_URL="postgresql+asyncpg://specula_app:specula@localhost:55432/{{db}}" just seed

# Two things to know before resetting the shared `specula`:
#   - It drops every row, including anything a live `prove-live` run ingested. If another
#     session is mid-ingest against this DB, you will pull the tenant out from under it.
#   - The downgrade walks back from whatever revision the DB is currently stamped at, so it
#     FAILS with "Can't locate revision" if that revision only exists on another branch.
#     Reset from the worktree whose migrations match the DB, or give that worktree its own
#     DB with `just db-bootstrap` — one database cannot serve two divergent heads.
#
# DESTRUCTIVE: drop to base, re-migrate, re-seed. just db-reset [db]
db-reset db="specula":
    DATABASE_URL="postgresql+asyncpg://specula_app:specula@localhost:55432/{{db}}" just migrate-down base
    DATABASE_URL="postgresql+asyncpg://specula_app:specula@localhost:55432/{{db}}" just migrate
    DATABASE_URL="postgresql+asyncpg://specula_app:specula@localhost:55432/{{db}}" just seed

# Regenerate the committed Linux pixel baselines in the pinned Playwright image
# (matches CI's Chromium + font stack). The visual config builds and serves a
# production `next start` inside the container (no dev overlay, no on-demand
# compile), so baselines are deterministic. Repo is mounted; node_modules is masked
# by anonymous volumes so the host's darwin install never leaks into the Linux
# container. Bump the image tag when @playwright/test is upgraded.
visual-update:
    docker run --rm \
      -v "{{justfile_directory()}}:/work" -w /work \
      -v /work/node_modules \
      -v /work/apps/web/node_modules \
      -v /work/packages/shared-types/node_modules \
      -e CI=1 \
      mcr.microsoft.com/playwright:v1.61.1-noble \
      bash -c "corepack enable && pnpm install --frozen-lockfile --config.store-dir=/tmp/pnpm-store && cd apps/web && pnpm exec playwright test --config playwright.visual.config.ts --update-snapshots=all"

# Run the visual suite in the pinned image WITHOUT updating (compare-only) —
# reproduces CI's pixel comparison locally.
visual:
    docker run --rm \
      -v "{{justfile_directory()}}:/work" -w /work \
      -v /work/node_modules \
      -v /work/apps/web/node_modules \
      -v /work/packages/shared-types/node_modules \
      -e CI=1 \
      mcr.microsoft.com/playwright:v1.61.1-noble \
      bash -c "corepack enable && pnpm install --frozen-lockfile --config.store-dir=/tmp/pnpm-store && cd apps/web && pnpm exec playwright test --config playwright.visual.config.ts"
