import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1) — so the
// auth guard is bypassed and the app views render without a Google login.
test("an authed visit to /jobs renders the Jobs view (no redirect)", async ({
  page,
}) => {
  // skip the once-per-session intro so it never covers the view (only the
  // intro spec tests the intro itself)
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1");
    } catch {}
  });
  await page.goto("/jobs");
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(
    page.getByRole("heading", { name: "Jobs", level: 1 }),
  ).toBeVisible();
});
