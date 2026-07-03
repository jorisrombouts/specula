import { test, expect } from "@playwright/test";

test("clicking a job row opens the drawer with the same title; Esc closes it", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1"); // skip intro
    } catch {}
  });
  await page.goto("/jobs");
  const firstRow = page.locator("article[data-fid]").first();
  await expect(firstRow).toBeVisible();
  const title = await firstRow.getByRole("heading", { level: 3 }).innerText();
  await firstRow.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("heading", { level: 2, name: title }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});
