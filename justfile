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
dev-web:
    cd apps/web && pnpm dev

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

# Test both apps
test:
    cd apps/api && uv run pytest

# Start local infra (Postgres + pgvector)
up:
    docker compose up -d

# Stop local infra
down:
    docker compose down
