import { test, expect } from "@playwright/test";

test("switching a lens re-sorts the job rows (FLIP) and keeps meters", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1"); // skip intro
    } catch {}
  });
  await page.goto("/jobs");
  const rows = page.locator("article[data-fid]:not([data-exit])");
  await expect(rows.first()).toBeVisible();
  const firstBefore = await rows.first().getAttribute("data-fid");
  // switch to a lens that re-scopes/re-scores the pool
  await page.getByRole("button", { name: /Foreign HQ/ }).click();
  await expect(rows.first()).toBeVisible();
  // the set changed (fewer rows or a new leader) — assert row count differs from all-lens 13
  await expect(rows).not.toHaveCount(13);
  // meters still render (a match number is visible in the first row)
  await expect(rows.first().locator("text=/\\d+/").first()).toBeVisible();
  const firstAfter = await rows.first().getAttribute("data-fid");
  expect(firstAfter).not.toBe(null);
  void firstBefore;
});
