import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1). The API
// webServer runs with PIPELINE_MODE=recorded (playwright.config.ts) so a
// triggered run completes without any live OpenAI/network calls.
//
// The demo user's seeded lens/targeting queries have no matching "recorded"
// discover fixtures, so the triggered run finalizes as status "done" with
// found/new: 0 and errors counted per missing-fixture query (verified by
// directly exercising run_discovery against the seeded demo user in
// PIPELINE_MODE=recorded — see the M3 frontend-wiring report). That's still a
// genuine terminal state with finishedAt set, so we assert on the syncing →
// not-syncing transition rather than a specific status, per the brief.
test("Refresh now triggers a run and the sidebar syncs to the new state", async ({
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

  const syncLine = page.locator("[data-sync-line]");
  const refreshButton = page.getByRole("button", { name: /refresh now/i });

  // Initial state: a finished run (the seeded demo run on a freshly-seeded
  // DB — "synced Nd ago · 7 new" — or a prior invocation of this same test,
  // since triggering a run necessarily mutates the shared dev DB's "latest
  // run". Assert only "some run has finished before", not specific stats, so
  // the test doesn't require a reseed between every local re-run.
  await expect(syncLine).toContainText("synced");
  await expect(refreshButton).toBeEnabled();

  await refreshButton.click();

  // Enters a syncing state.
  const syncingButton = page.getByRole("button", { name: /syncing/i });
  await expect(syncingButton).toBeVisible();
  await expect(syncingButton).toBeDisabled();

  // Polls (~3s) until the triggered run reaches a terminal status — the
  // button becomes "Refresh now" again.
  await expect(refreshButton).toBeVisible({ timeout: 30_000 });
  await expect(refreshButton).toBeEnabled();

  // The sync line now reflects the just-finished run, not the stale seeded
  // one (whose relative time is days old by the time this suite runs).
  await expect(syncLine).toContainText("just now");
});
