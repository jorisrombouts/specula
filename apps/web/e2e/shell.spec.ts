import { test, expect } from "@playwright/test";

test("the app renders on warm paper", async ({ page }) => {
  await page.goto("/");
  const bg = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  // --paper #FBFAF6 == rgb(251, 250, 246)
  expect(bg).toBe("rgb(251, 250, 246)");
});
