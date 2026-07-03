import { test as base, expect, type Page } from "@playwright/test";

// A page pre-stabilized for pixel snapshots: the once-per-session intro is
// skipped so it never covers a view, and reduced-motion is emulated so
// count-ups render final values.
export const test = base.extend<{ stablePage: Page }>({
  stablePage: async ({ page }, use) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.setItem("specula_intro", "1");
      } catch {
        /* ignore */
      }
    });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await use(page);
  },
});

export { expect };

// Stabilize the page for a full-page screenshot. The app shell is a fixed-height
// (`h-screen`) grid with an inner `main-scroll` scroll container, so the document
// itself never grows and `fullPage` would clip everything below the fold.
// Neutralize the height/overflow so the page flows to its natural full height and
// `fullPage` captures the whole view. (On the public sign-in page the `:has`
// selector simply matches nothing — a harmless no-op.) Then wait for the network
// to settle and the self-hosted fonts to paint.
export async function stabilize(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.addStyleTag({
    content: `
      div:has(> main.main-scroll) { height: auto !important; overflow: visible !important; }
      main.main-scroll { height: auto !important; overflow: visible !important; }
    `,
  });
  await page.evaluate(() => document.fonts.ready.then(() => true));
}
