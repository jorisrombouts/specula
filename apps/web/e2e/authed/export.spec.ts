import { readFile } from "node:fs/promises";
import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1).
//
// Targets the DATA lane's account export (/settings → "Export my data" downloads an
// ExportBundle JSON: candidate, targeting, companies, postings, scores, lenses, runs,
// llmCosts — skills_taxonomy is global and excluded).
//
// The export control is a plain `<a href="/api/account/export" download>` (role
// "link", not "button" — see settings-view.tsx), not a JS-driven button.

test.describe("Data export", () => {
  test("downloads the tenant's export bundle as JSON", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.setItem("specula_intro", "1");
      } catch {}
    });
    await page.goto("/settings");
    await expect(
      page.getByRole("heading", { name: "Settings", level: 1 }),
    ).toBeVisible();

    const exportLink = page.getByRole("link", { name: /export/i });
    await expect(exportLink).toBeVisible();

    // The click triggers a file download (a browser save, not a navigation) —
    // the anchor's `download` attribute intercepts the navigation.
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      exportLink.click(),
    ]);

    // The bundle is JSON. Assert on the download, then that it parses into the
    // ExportBundle shape (exportedAt + the per-tenant collections).
    expect(download.suggestedFilename()).toMatch(/\.json$/);
    const path = await download.path();
    const bundle = JSON.parse(await readFile(path, "utf8")) as {
      exportedAt?: unknown;
      postings?: unknown;
      llmCosts?: unknown;
      skillsTaxonomy?: unknown;
    };
    expect(bundle).toHaveProperty("exportedAt");
    expect(Array.isArray(bundle.postings)).toBe(true);
    expect(Array.isArray(bundle.llmCosts)).toBe(true);
    // skills_taxonomy is global/unscoped and must NOT be in a per-tenant export.
    expect(bundle).not.toHaveProperty("skillsTaxonomy");
  });
});
