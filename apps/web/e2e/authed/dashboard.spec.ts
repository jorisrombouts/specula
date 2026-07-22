import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1) — the auth
// guard is bypassed and views render the seeded demo tenant's real data.
//
// Targets the DASH lane's cost dashboard (/dashboard rendering a DashboardSummary:
// totalCostUsd + costByStage + costByDay + recentRuns).
//
// Self-sufficient by design: seed.py creates no llm_costs rows, so on a freshly-seeded
// DB the "Spend by stage" panel renders its "No spend recorded yet." empty state
// (dashboard-view.tsx) rather than per-stage rows. The stage assertion below accepts
// either so this spec passes regardless of whether any run has generated cost data —
// it doesn't depend on another spec (e.g. refresh.spec.ts) having run first.

test.describe("Dashboard renders spend", () => {
  test("shows the total LLM spend and the per-stage breakdown", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.setItem("specula_intro", "1");
      } catch {}
    });
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(
      page.getByRole("heading", { name: "Dashboard", level: 1 }),
    ).toBeVisible();

    // totalCostUsd always renders as a USD figure (the "Total LLM spend" tile shows
    // "$0.00" when there's no spend yet, never a placeholder) — present regardless
    // of whether the seed produced any llm_costs rows.
    await expect(page.getByText(/\$\s?\d/).first()).toBeVisible();

    // costByStage drives a per-stage breakdown. Accept either a real stage label
    // (cost data exists) or the panel's empty state (a fresh seed has none) — see
    // the file header for why both are valid here.
    await expect(
      page
        .getByText(/extract|score|discover|embed|enrich|no spend recorded yet/i)
        .first(),
    ).toBeVisible();
  });
});
