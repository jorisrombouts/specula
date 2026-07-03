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

// Navigate to a route, stabilize, then size the viewport to the full content
// height so the caller can take a plain viewport screenshot of the whole view.
// (A viewport shot, not Playwright's `fullPage`: the app shell scrolls its inner
// panel, not the document, so we grow the viewport to the content instead.)
export async function gotoStable(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "networkidle" });
  await stabilize(page);
  const h = await page.evaluate(() =>
    Math.ceil(document.documentElement.scrollHeight),
  );
  await page.setViewportSize({ width: 1440, height: Math.max(900, h) });
  await page.waitForTimeout(400);
}

// Stabilize the page for the screenshot. The app shell is a fixed-height
// (`h-screen`) grid with an inner `main-scroll` scroll container, so the document
// itself never grows and a naive capture would clip everything below the fold.
// Neutralize the height/overflow so the page flows to its natural full height and
// `document.documentElement.scrollHeight` reports the real content height. (On the
// public sign-in page the `:has` selector simply matches nothing — a harmless
// no-op.) Then wait for the network to settle and the self-hosted fonts to paint.
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
