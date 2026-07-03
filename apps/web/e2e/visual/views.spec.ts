import { test, expect, gotoStable } from "./fixtures";

test("signin page", async ({ stablePage: page }) => {
  await gotoStable(page, "/signin");
  await expect(page).toHaveScreenshot("signin.png");
});

test("jobs view", async ({ stablePage: page }) => {
  await gotoStable(page, "/jobs");
  await expect(page).toHaveScreenshot("jobs.png");
});

test("jobs view — drawer open", async ({ stablePage: page }) => {
  // Capture the drawer as the user sees it on open: the fixed panel over the
  // scrim-dimmed Jobs list. A viewport shot — the drawer is a fixed,
  // viewport-height overlay, so this is its faithful appearance. The dev-overlay
  // hide is installed by the stablePage fixture (init script + observer).
  await page.goto("/jobs", { waitUntil: "networkidle" });
  await page.locator("article[data-fid]").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => true));
  await expect(page).toHaveScreenshot("jobs-drawer.png");
});

for (const [name, path] of [
  ["approvals", "/approvals"],
  ["companies", "/companies"],
  ["insights", "/insights"],
  ["profiles", "/profiles"],
  ["candidate", "/candidate"],
  ["targeting", "/targeting"],
] as const) {
  test(`${name} view`, async ({ stablePage: page }) => {
    await gotoStable(page, path);
    await expect(page).toHaveScreenshot(`${name}.png`);
  });
}
