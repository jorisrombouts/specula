import { defineConfig, devices } from "@playwright/test";
import {
  E2E_API_URL,
  E2E_DATABASE_URL,
  E2E_SERVICE_JWT_SECRET,
} from "./e2e/visual/auth";

// Functional E2E harness (dev servers). The pixel-regression suite lives in its
// own config — playwright.visual.config.ts — because it needs a production build,
// not a dev server. The `visual/` specs are ignored here.
export default defineConfig({
  testDir: "./e2e",
  testIgnore: /visual\//,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: { trace: "on-first-retry" },
  projects: [
    {
      name: "public",
      testIgnore: [/authed\//, /visual\//],
      use: { ...devices["Desktop Chrome"], baseURL: "http://localhost:3000" },
    },
    {
      name: "authed",
      testMatch: /authed\//,
      use: { ...devices["Desktop Chrome"], baseURL: "http://localhost:3001" },
    },
  ],
  webServer: [
    {
      // FastAPI the authed app fetches from. Its DB must be pre-seeded (the `just e2e`
      // recipe / CI job seed it). reuseExistingServer so a host uvicorn is reused.
      command: "uv run uvicorn specula_api.main:app --port 8000",
      cwd: "../api",
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        SERVICE_JWT_SECRET: E2E_SERVICE_JWT_SECRET,
        DATABASE_URL: E2E_DATABASE_URL,
        // A triggered run (authed/refresh.spec.ts) must complete without live
        // OpenAI/network calls — "recorded" replays fixtures instead. No
        // PIPELINE_FIXTURES_DIR override: build_deps' default already points at
        // apps/api/tests/fixtures/pipeline.
        PIPELINE_MODE: "recorded",
      },
    },
    {
      command: "pnpm dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "pnpm dev --port 3001",
      url: "http://localhost:3001",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      // Separate dist dir: `next dev` shares build state per-directory, so two
      // instances in the same apps/web dir would corrupt each other's route
      // manifests. See the comment in next.config.ts.
      // Under DEV_AUTH_BYPASS, bffFetch mints for the seeded demo user (see bff.ts),
      // so the authed views fetch real seeded data from FastAPI.
      env: {
        DEV_AUTH_BYPASS: "1",
        NEXT_DIST_DIR: ".next-authed",
        SERVICE_JWT_SECRET: E2E_SERVICE_JWT_SECRET,
        API_URL: E2E_API_URL,
      },
    },
  ],
});
