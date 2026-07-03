import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: { trace: "on-first-retry" },
  projects: [
    {
      name: "public",
      testIgnore: /authed\//,
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
      env: { DEV_AUTH_BYPASS: "1", NEXT_DIST_DIR: ".next-authed" },
    },
  ],
});
