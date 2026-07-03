import { test, expect } from "@playwright/test";

test("the tweaks panel opens, applies an accent, and persists across reload", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1"); // skip intro
    } catch {}
  });
  await page.goto("/jobs");
  await page.getByRole("button", { name: /tweaks/i }).click();
  // pick the blue accent (#2D5BBF)
  await page.getByRole("radio", { name: "#2D5BBF" }).click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--accent").trim(),
      ),
    )
    .toBe("#2D5BBF");
  // persisted → survives reload
  await page.reload();
  await expect
    .poll(() =>
      page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--accent").trim(),
      ),
    )
    .toBe("#2D5BBF");
});
