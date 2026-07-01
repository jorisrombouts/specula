set shell := ["bash", "-uc"]

# Install all deps and git hooks
setup:
    cd apps/api && uv sync
    cd apps/web && pnpm install
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
