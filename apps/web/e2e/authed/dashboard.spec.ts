import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1) — the auth
// guard is bypassed and views render the seeded demo tenant's real data.
//
// Targets the DASH lane's cost dashboard (/dashboard rendering a DashboardSummary:
// totalCostUsd + costByStage + costByDay + recentRuns). LOAD merges LAST and rebases
// onto the integrated main; until DASH is on this branch there is no (app)/dashboard
// page and GET /api/v1/dashboard is the `{status:not_implemented}` stub. Per the LOAD
// brief we SKIP rather than assert against that stub.
//
// After rebasing onto the integrated main: flip PENDING → false and tighten the
// selectors against the real DASH DOM. See .lane-status.md.
const PENDING = true;

test.describe("Dashboard renders spend", () => {
  test.beforeEach(() => {
    test.skip(
      PENDING,
      "Pending DASH lane merge — /dashboard view not on this branch yet",
    );
  });

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

    // totalCostUsd is rendered as a USD figure. The seeded tenant has cost rows,
    // so a dollar amount is present (counts/figures are derived server-side).
    await expect(page.getByText(/\$\s?\d/).first()).toBeVisible();

    // costByStage drives a per-stage breakdown; recentRuns lists the latest runs.
    // At least one known pipeline stage label surfaces.
    await expect(
      page.getByText(/extract|score|discover|embed|enrich/i).first(),
    ).toBeVisible();
  });
});
