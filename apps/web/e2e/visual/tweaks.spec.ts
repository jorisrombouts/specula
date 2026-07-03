import { test, expect, gotoStable } from "./fixtures";

// The Tweaks panel lets a viewer restyle the app (match-meter style, list layout,
// …); the choice persists in `localStorage.specula_tweaks` and is applied by the
// FOUC init script + provider on boot. These snapshots lock the two structural
// tweaks — the cards layout and the ring meters — so a regression in either is
// caught. We seed the tweak via an init script (deterministic — no clicking
// through the panel), then confirm it took before shooting.

test("jobs view — cards layout", async ({ stablePage: page }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "specula_tweaks",
        JSON.stringify({ layout: "cards" }),
      );
    } catch {
      /* ignore */
    }
  });
  await gotoStable(page, "/jobs");
  await expect(page.locator("[data-jlist][data-cards]")).toBeVisible();
  await expect(page).toHaveScreenshot("jobs-cards.png");
});

test("jobs view — ring meters", async ({ stablePage: page }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "specula_tweaks",
        JSON.stringify({ mstyle: "ring" }),
      );
    } catch {
      /* ignore */
    }
  });
  await gotoStable(page, "/jobs");
  await expect(page.locator('[data-style="ring"]').first()).toBeVisible();
  await expect(page).toHaveScreenshot("jobs-ring.png");
});
