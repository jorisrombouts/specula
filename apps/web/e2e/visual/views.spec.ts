import { test, expect, stabilize } from "./fixtures";

test("jobs view", async ({ stablePage: page }) => {
  await page.goto("/jobs");
  await stabilize(page);
  await expect(page).toHaveScreenshot("jobs.png", { fullPage: true });
});
