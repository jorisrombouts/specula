import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1). The API webServer
// runs with PIPELINE_MODE=recorded (playwright.config.ts) so a triggered run completes
// without live OpenAI/network calls.
//
// Targets the NET lane's on-demand trigger rate-limit: past run_cooldown_s /
// run_rate_limit_per_hour, POST /api/v1/runs returns 429 (RateLimitError:
// {error:"rate_limited", retryAfterS}) and the "Refresh now" flow surfaces it to the
// user instead of silently doing nothing. LOAD merges LAST and rebases onto the
// integrated main; the cap config exists but no enforcement is on this branch, so we
// SKIP rather than assert against un-enforced behavior.
//
// After rebasing onto the integrated main: flip PENDING → false and tighten the
// selector for the surfaced message against the real NET/DASH DOM. See .lane-status.md.
const PENDING = true;

test.describe("Run-trigger rate limit", () => {
  test.beforeEach(() => {
    test.skip(
      PENDING,
      "Pending NET lane merge — trigger rate-limit not enforced on this branch",
    );
  });

  test("a second trigger inside the cooldown surfaces the 429 to the user", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.setItem("specula_intro", "1");
      } catch {}
    });
    await page.goto("/jobs");
    await expect(
      page.getByRole("heading", { name: "Jobs", level: 1 }),
    ).toBeVisible();

    const refreshButton = page.getByRole("button", { name: /refresh now/i });
    await expect(refreshButton).toBeEnabled();

    // First trigger: accepted. Runs (recorded) then returns to "Refresh now".
    await refreshButton.click();
    await expect(refreshButton).toBeEnabled({ timeout: 30_000 });

    // Second trigger inside run_cooldown_s → the API rate-limits it. The UI must
    // surface that (a rate-limit / retry-after message), not silently swallow it.
    await refreshButton.click();
    await expect(
      page.getByText(/rate.?limit|too many|try again|wait\s+\d/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });
});
