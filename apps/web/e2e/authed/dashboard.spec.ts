import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1) — the auth
// guard is bypassed and views render the seeded demo tenant's real data.
//
// Targets the DASH lane's token dashboard (/dashboard rendering a DashboardSummary:
// totalTokens + tokensByStage + tokensByDay + recentRuns).
//
// Self-sufficient by design: seed.py creates no llm_costs rows, so on a freshly-seeded
// DB the "Tokens by stage" panel renders its "No tokens recorded yet." empty state
// (dashboard-view.tsx) rather than per-stage rows. The stage assertion below accepts
// either so this spec passes regardless of whether any run has generated usage data —
// it doesn't depend on another spec (e.g. refresh.spec.ts) having run first.

test.describe("Dashboard renders tokens", () => {
  test("shows the total LLM tokens and the per-stage breakdown", async ({
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

    // The "Total LLM tokens" tile's value renders in a sibling div next to the label (see
    // the `Tile` component in dashboard-view.tsx) — assert it's actually digits (optionally
    // comma-grouped), not just that the label is present. This is present regardless of
    // whether the seed produced any llm_costs rows: "0" when nothing has been recorded yet.
    const tokensLabel = page.getByText("Total LLM tokens", { exact: true });
    await expect(tokensLabel).toBeVisible();
    await expect(
      tokensLabel.locator("xpath=following-sibling::div[1]"),
    ).toHaveText(/^[\d,]+$/);

    // tokensByStage drives a per-stage breakdown. Accept either a real stage label
    // (usage data exists) or the panel's empty state (a fresh seed has none) — see
    // the file header for why both are valid here.
    await expect(
      page
        .getByText(
          /extract|score|discover|embed|enrich|no tokens recorded yet/i,
        )
        .first(),
    ).toBeVisible();
  });
});
