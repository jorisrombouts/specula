import { defineConfig, devices } from "@playwright/test";
import {
  E2E_API_URL,
  E2E_AUTH_SECRET,
  E2E_DATABASE_URL,
  E2E_SERVICE_JWT_SECRET,
  STORAGE_STATE,
  VISUAL_PORT,
} from "./e2e/visual/auth";

// Pixel-regression harness. Unlike the E2E config (which drives the dev servers),
// the visual suite screenshots a real production build: `next build && next start`
// has no dev overlay and no on-demand compilation, so captures are deterministic —
// the dev "Compiling…" indicator can never land in a baseline. Auth uses a minted
// Auth.js session cookie (see e2e/visual/global-setup.ts) since the production
// build disables the dev bypass.
const baseURL = `http://localhost:${VISUAL_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /visual\/.*\.spec\.ts$/,
  // Snapshots must be byte-stable; run serially rather than racing captures.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  globalSetup: "./e2e/visual/global-setup.ts",
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
    },
  },
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    viewport: { width: 1440, height: 900 },
    storageState: STORAGE_STATE,
    trace: "on-first-retry",
  },
  projects: [{ name: "visual" }],
  webServer: [
    {
      // FastAPI the production build fetches its data from. The DB it points at must
      // already be seeded (the `just visual*` recipe / CI job seed it before running).
      // Locally reuse a host uvicorn if present; in CI always start fresh.
      command: "uv run uvicorn specula_api.main:app --port 8000",
      cwd: "../api",
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        SERVICE_JWT_SECRET: E2E_SERVICE_JWT_SECRET,
        DATABASE_URL: E2E_DATABASE_URL,
      },
    },
    {
      // Self-contained: build then serve, so a clean checkout works with no
      // preconditions. `reuseExistingServer` skips the rebuild when a server is
      // already up locally.
      command: `pnpm exec next build && pnpm exec next start --port ${VISUAL_PORT}`,
      url: baseURL,
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
      env: {
        // Production mode: dev overlay off, dev auth bypass disabled. AUTH_SECRET
        // matches the secret global-setup signs the session cookie with; TRUST_HOST
        // lets Auth.js accept the localhost origin.
        NODE_ENV: "production",
        AUTH_SECRET: E2E_AUTH_SECRET,
        AUTH_TRUST_HOST: "true",
        AUTH_URL: baseURL,
        // The prod build (bypass disabled) mints a service JWT from the minted cookie
        // and calls FastAPI for real data.
        SERVICE_JWT_SECRET: E2E_SERVICE_JWT_SECRET,
        API_URL: E2E_API_URL,
      },
    },
  ],
});
