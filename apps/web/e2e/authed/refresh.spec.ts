import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1). The API
// webServer runs with PIPELINE_MODE=recorded (playwright.config.ts) so a
// triggered run completes without any live OpenAI/network calls.
//
// The discovery trigger lives in the Approvals header ("Find new companies") —
// discovery stages candidate companies into that queue, so the button sits where
// the results land. It was the sidebar's "Refresh now" until the header-refresh
// split; this spec follows it there.
//
// The demo user's seeded lens/targeting queries have no matching "recorded"
// discover fixtures, so the triggered run finalizes as status "done" with
// found/new: 0 and errors counted per missing-fixture query (verified by
// directly exercising run_discovery against the seeded demo user in
// PIPELINE_MODE=recorded — see the M3 frontend-wiring report). That's still a
// genuine terminal state with finishedAt set, so we assert on the searching →
// not-searching transition rather than a specific status, per the brief.
test("Find new companies triggers a run and the header syncs to the new state", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1");
    } catch {}
  });
  await page.goto("/approvals");
  await expect(
    page.getByRole("heading", { name: "Approval queue", level: 1 }),
  ).toBeVisible();

  const syncLine = page.locator("[data-sync-line]");
  const findButton = page.getByRole("button", { name: /find new companies/i });

  // Initial state: a finished run (the seeded demo run on a freshly-seeded
  // DB — "checked 20d ago" — or a prior invocation of this same test, since
  // triggering a run necessarily mutates the shared dev DB's "latest run".
  // Assert only "some run has finished before", not a specific age, so the
  // test doesn't require a reseed between every local re-run.
  await expect(syncLine).toContainText("checked");
  await expect(findButton).toBeEnabled();

  await findButton.click();

  // Enters a searching state. The status line is hidden while a run is in
  // flight, so it's only asserted on either side of the transition.
  const searchingButton = page.getByRole("button", { name: /searching/i });
  await expect(searchingButton).toBeVisible();
  await expect(searchingButton).toBeDisabled();

  // Polls (~3s) until the triggered run reaches a terminal status — the
  // button becomes "Find new companies" again.
  await expect(findButton).toBeVisible({ timeout: 30_000 });
  await expect(findButton).toBeEnabled();

  // The status line now reflects the just-finished run, not the stale seeded
  // one (whose relative time is days old by the time this suite runs).
  await expect(syncLine).toContainText("just now");
});
