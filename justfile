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

# Regenerate the committed Linux pixel baselines in the pinned Playwright image
# (matches CI's Chromium + font stack). Repo is mounted; node_modules is masked
# by anonymous volumes so the host's darwin install never leaks into the Linux
# container. Playwright starts its own dev server inside the container, so no
# host networking is needed. Bump the image tag when @playwright/test is upgraded.
visual-update:
    docker run --rm \
      -v "{{justfile_directory()}}:/work" -w /work \
      -v /work/node_modules \
      -v /work/apps/web/node_modules \
      -v /work/packages/shared-types/node_modules \
      -e CI=1 \
      mcr.microsoft.com/playwright:v1.61.1-noble \
      bash -c "corepack enable && pnpm install --frozen-lockfile && cd apps/web && pnpm exec playwright test --project=visual --update-snapshots"

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
      bash -c "corepack enable && pnpm install --frozen-lockfile && cd apps/web && pnpm exec playwright test --project=visual"
