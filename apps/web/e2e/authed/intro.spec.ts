import { test, expect } from "@playwright/test";

test("the assembling intro shows on first load, dismisses on click, and does not recur", async ({
  page,
}) => {
  await page.goto("/jobs");
  // Scoped to the intro's own mark (a <div>) — the sidebar also renders a
  // persistent "Specula" brand label (a <span>) for the whole authed session.
  const mark = page.locator("div").filter({ hasText: /^Specula$/ });
  await expect(mark).toBeVisible();
  await page.mouse.click(400, 400); // "click anywhere to enter"
  await expect(mark).toBeHidden();
  // a second navigation in the same session does NOT re-show it
  await page.goto("/companies");
  await expect(
    page.locator("div").filter({ hasText: /^Specula$/ }),
  ).toBeHidden();
});
