# M1d-2 — Pixel visual-regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the pixel-faithful design port with a deterministic Playwright `toHaveScreenshot` suite (~11 states), compared against committed Linux baselines generated in the pinned Playwright Docker image, gated in CI.

**Architecture:** A separate `visual` Playwright project (served by the `:3001` bypass server, which renders every route) with a shared determinism fixture (intro-skip, reduced-motion, fonts-ready) and `animations: "disabled"` (freezes the M1c motion to stable end-frames). Baselines are `*-linux.png`, generated only via a `just visual-update` Docker recipe (matching CI's renderer) and committed; CI's native Linux Chromium compares against them and fails the build on an unexpected diff.

**Tech Stack:** Playwright 1.61.1 (`toHaveScreenshot`), Docker (`mcr.microsoft.com/playwright:v1.61.1-noble`), the existing two-server harness + `DEV_AUTH_BYPASS`.

## Global Constraints

- **Baselines are Linux, committed, Docker-generated.** Only `*-linux.png` are committed (under `apps/web/e2e/visual/**-snapshots/`). They are generated ONLY via `just visual-update` (the pinned Docker image = CI's Chromium + font stack). A macOS dev never commits a `*-darwin.png` (a `.gitignore` guard blocks it). **This is controller-verified:** the person running the task eyeballs each generated PNG before committing — a wrong baseline silently locks in a wrong render.
- **Determinism is mandatory.** Every snapshot: skip the intro (`sessionStorage.specula_intro=1` via `addInitScript`), `emulateMedia({ reducedMotion: "reduce" })`, `animations: "disabled"` (config), wait `document.fonts.ready` + `networkidle` before shooting, fixed viewport `1440×900`, `fullPage: true`. The seed is static + no live dates → content is inherently stable.
- **The `visual` project is served by the `:3001` bypass server** (`DEV_AUTH_BYPASS=1`, dev-only gate intact — never a prod build). It renders `/signin` AND the app views.
- **Tolerance:** `maxDiffPixelRatio: 0.01`, `threshold: 0.2` (config-level) — absorbs sub-pixel AA noise, still catches real changes.
- **No product code changes** — additive test infra only. TypeScript strict. Commands run from `apps/web` unless a `just` recipe (repo root).
- **The Docker image tag `v1.61.1-noble` is pinned to `@playwright/test@1.61.1`** — bump both together on upgrade.
- **Sources of truth:** spec `docs/superpowers/specs/2026-07-03-m1d-2-visual-regression-design.md`; the built app; `apps/web/playwright.config.ts`; `.github/workflows/ci.yml`.

---

### Task 1: Pipeline bring-up + first snapshot (`jobs`)

Front-loads ALL pipeline risk on one snapshot: the `visual` project config, the determinism fixture, the Docker recipes, and one baseline — proving Docker generation + the gate end-to-end before adding the rest.

**Files:**
- Modify: `apps/web/playwright.config.ts`
- Create: `apps/web/e2e/visual/fixtures.ts`, `apps/web/e2e/visual/views.spec.ts`
- Modify: `justfile` (repo root)
- Create (committed baseline, Docker-generated): `apps/web/e2e/visual/views.spec.ts-snapshots/jobs-chromium-linux.png`

**Interfaces:**
- Produces:
  - `test` + `expect` (Playwright test extended with a `stablePage` fixture) + `stabilize(page)` helper, from `e2e/visual/fixtures.ts`.
  - a `visual` Playwright project (matches `e2e/visual/`, baseURL `:3001`, viewport 1440×900).
  - `just visual-update` (regenerate Linux baselines in Docker) + `just visual` (compare-only in Docker).

- [ ] **Step 1: Add the `visual` project + screenshot config to `playwright.config.ts`**

Add the screenshot config to the top-level `defineConfig` (a new `expect` key) and a third project. Insert the `expect` block after `use: { trace: "on-first-retry" },`:

```ts
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
    },
  },
```

And add this project to the `projects: [...]` array (after the `authed` project):

```ts
    {
      name: "visual",
      testMatch: /visual\//,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:3001",
        viewport: { width: 1440, height: 900 },
      },
    },
```

(The `authed` project's `testMatch: /authed\//` already excludes `e2e/visual/`; the `public` project's `testIgnore: /authed\//` would MATCH `e2e/visual/` — so also add `, /visual\//` to the public project's `testIgnore` so it becomes `testIgnore: [/authed\//, /visual\//]`. Update it:)

```ts
      name: "public",
      testIgnore: [/authed\//, /visual\//],
```

- [ ] **Step 2: Create the determinism fixture**

Create `apps/web/e2e/visual/fixtures.ts`:

```ts
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

// Wait for the network to settle and the (self-hosted) fonts to finish
// loading, so the serif faces are painted before the screenshot.
export async function stabilize(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready.then(() => true));
}
```

- [ ] **Step 3: Create `views.spec.ts` with the single `jobs` snapshot**

Create `apps/web/e2e/visual/views.spec.ts`:

```ts
import { test, expect, stabilize } from "./fixtures";

test("jobs view", async ({ stablePage: page }) => {
  await page.goto("/jobs");
  await stabilize(page);
  await expect(page).toHaveScreenshot("jobs.png", { fullPage: true });
});
```

- [ ] **Step 4: Add the `just` recipes**

Append to the repo-root `justfile`:

```makefile
# Regenerate the committed Linux pixel baselines in the pinned Playwright image
# (matches CI's Chromium + font stack). Repo is mounted; node_modules is masked
# by anonymous volumes so the host's darwin install never leaks into the Linux
# container. Playwright starts its own dev server inside the container, so no
# host networking is needed. Bump the image tag when @playwright/test is upgraded.
visual-update:
    docker run --rm \
      -v "{{justfile_directory()}}:/work" -w /work \
      -v /work/node_modules \
      -v /work/apps/web/node_modules \
      -v /work/packages/shared-types/node_modules \
      -e CI=1 \
      mcr.microsoft.com/playwright:v1.61.1-noble \
      bash -c "corepack enable && pnpm install --frozen-lockfile && cd apps/web && pnpm exec playwright test --project=visual --update-snapshots"

# Run the visual suite in the pinned image WITHOUT updating (compare-only) —
# reproduces CI's pixel comparison locally.
visual:
    docker run --rm \
      -v "{{justfile_directory()}}:/work" -w /work \
      -v /work/node_modules \
      -v /work/apps/web/node_modules \
      -v /work/packages/shared-types/node_modules \
      -e CI=1 \
      mcr.microsoft.com/playwright:v1.61.1-noble \
      bash -c "corepack enable && pnpm install --frozen-lockfile && cd apps/web && pnpm exec playwright test --project=visual"
```

- [ ] **Step 5: Generate the `jobs` baseline in Docker**

Run (from repo root): `just visual-update`
Expected: Docker pulls `v1.61.1-noble` (first run only), installs deps, starts the :3001 server, and writes `apps/web/e2e/visual/views.spec.ts-snapshots/jobs-chromium-linux.png`. The run reports the snapshot was written/updated.
(If the image pull or install is slow, that's expected on the first run — subsequent runs reuse the pulled image.)

- [ ] **Step 6: Eyeball the baseline (CONTROLLER-VERIFIED)**

Open `apps/web/e2e/visual/views.spec.ts-snapshots/jobs-chromium-linux.png` and confirm it's a correct, complete render of the Jobs view (lens bar, rows, meters, banner — no intro overlay, no half-loaded fonts, no cut-off content). A wrong baseline here locks in a wrong render. Only proceed once it looks right.

- [ ] **Step 7: Confirm the gate passes against the committed baseline**

Run (from repo root): `just visual`
Expected: PASS (1 passed) — the freshly-minted baseline matches a fresh render.

- [ ] **Step 8: Commit**

```bash
git add apps/web/playwright.config.ts apps/web/e2e/visual/fixtures.ts apps/web/e2e/visual/views.spec.ts "apps/web/e2e/visual/views.spec.ts-snapshots/jobs-chromium-linux.png" justfile
git commit -m "test(web): visual-regression pipeline + jobs snapshot (Docker Linux baselines) (M1d-2)"
```

---

### Task 2: The remaining view snapshots

**Files:**
- Modify: `apps/web/e2e/visual/views.spec.ts`
- Create (committed baselines, Docker-generated): `apps/web/e2e/visual/views.spec.ts-snapshots/{signin,approvals,companies,insights,profiles,candidate,targeting,jobs-drawer}-chromium-linux.png`

**Interfaces:**
- Consumes: `test`/`expect`/`stabilize` (Task 1); `just visual-update`/`just visual` (Task 1).

- [ ] **Step 1: Add the remaining view snapshots to `views.spec.ts`**

Replace `apps/web/e2e/visual/views.spec.ts` with (keeps the `jobs` test, adds the rest):

```ts
import { test, expect, stabilize } from "./fixtures";

test("signin page", async ({ stablePage: page }) => {
  await page.goto("/signin");
  await stabilize(page);
  await expect(page).toHaveScreenshot("signin.png", { fullPage: true });
});

test("jobs view", async ({ stablePage: page }) => {
  await page.goto("/jobs");
  await stabilize(page);
  await expect(page).toHaveScreenshot("jobs.png", { fullPage: true });
});

test("jobs view — drawer open", async ({ stablePage: page }) => {
  await page.goto("/jobs");
  await stabilize(page);
  await page.locator("article[data-fid]").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await stabilize(page);
  await expect(page).toHaveScreenshot("jobs-drawer.png", { fullPage: true });
});

for (const [name, path] of [
  ["approvals", "/approvals"],
  ["companies", "/companies"],
  ["insights", "/insights"],
  ["profiles", "/profiles"],
  ["candidate", "/candidate"],
  ["targeting", "/targeting"],
] as const) {
  test(`${name} view`, async ({ stablePage: page }) => {
    await page.goto(path);
    await stabilize(page);
    await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true });
  });
}
```

- [ ] **Step 2: Generate the new baselines in Docker**

Run: `just visual-update`
Expected: writes the 8 new `*-chromium-linux.png` baselines (signin, jobs-drawer, approvals, companies, insights, profiles, candidate, targeting) alongside the existing `jobs`. Reports all snapshots written/updated.

- [ ] **Step 3: Eyeball ALL new baselines (CONTROLLER-VERIFIED)**

Open each new PNG under `apps/web/e2e/visual/views.spec.ts-snapshots/` and confirm each is a correct, complete render of its view (the drawer one shows the drawer open over Jobs with all sections; the tall views — insights/candidate — are fully captured; fonts loaded; no intro). Only proceed once every one looks right.

- [ ] **Step 4: Confirm the gate passes**

Run: `just visual`
Expected: PASS (9 passed) — all baselines match fresh renders.

- [ ] **Step 5: Commit**

```bash
git add apps/web/e2e/visual/views.spec.ts apps/web/e2e/visual/views.spec.ts-snapshots
git commit -m "test(web): snapshot signin + read/config views + drawer (M1d-2)"
```

---

### Task 3: Tweaked-state snapshots (cards + ring)

**Files:**
- Create: `apps/web/e2e/visual/tweaks.spec.ts`
- Create (committed baselines, Docker-generated): `apps/web/e2e/visual/tweaks.spec.ts-snapshots/{jobs-cards,jobs-ring}-chromium-linux.png`

**Interfaces:**
- Consumes: `test`/`expect`/`stabilize` (Task 1). Sets the tweak via `localStorage` in an init script (deterministic — no clicking through the panel), matching the `specula_tweaks` key + `applyTweaks` mapping the app reads.

- [ ] **Step 1: Create `tweaks.spec.ts`**

Create `apps/web/e2e/visual/tweaks.spec.ts`. Each test seeds `localStorage.specula_tweaks` before load (via `addInitScript`) so the app boots into the tweaked state — the FOUC init script + provider apply it deterministically.

```ts
import { test, expect, stabilize } from "./fixtures";

test("jobs view — cards layout", async ({ stablePage: page }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("specula_tweaks", JSON.stringify({ layout: "cards" }));
    } catch {
      /* ignore */
    }
  });
  await page.goto("/jobs");
  await stabilize(page);
  // confirm the tweak took (the card grid rendered) before shooting
  await expect(page.locator("[data-jlist][data-cards]")).toBeVisible();
  await expect(page).toHaveScreenshot("jobs-cards.png", { fullPage: true });
});

test("jobs view — ring meters", async ({ stablePage: page }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("specula_tweaks", JSON.stringify({ mstyle: "ring" }));
    } catch {
      /* ignore */
    }
  });
  await page.goto("/jobs");
  await stabilize(page);
  await expect(page.locator('[data-style="ring"]').first()).toBeVisible();
  await expect(page).toHaveScreenshot("jobs-ring.png", { fullPage: true });
});
```

- [ ] **Step 2: Generate the baselines in Docker**

Run: `just visual-update`
Expected: writes `jobs-cards-chromium-linux.png` + `jobs-ring-chromium-linux.png` under `apps/web/e2e/visual/tweaks.spec.ts-snapshots/` (plus re-verifies the `views.spec.ts` ones, unchanged).

- [ ] **Step 3: Eyeball the two baselines (CONTROLLER-VERIFIED)**

Confirm `jobs-cards` shows the 2-col bordered-card grid (no colhead, no index, full-width meters) and `jobs-ring` shows the conic-ring meters. Only proceed once both look right.

- [ ] **Step 4: Confirm the gate passes**

Run: `just visual`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/web/e2e/visual/tweaks.spec.ts apps/web/e2e/visual/tweaks.spec.ts-snapshots
git commit -m "test(web): snapshot cards-layout + ring-meter tweaked states (M1d-2)"
```

---

### Task 4: CI failure-artifact + darwin-baseline guard + prove-the-gate

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `apps/web/.gitignore`

**Interfaces:**
- Consumes: the `visual` project (Task 1) — already run by the existing `pnpm test:e2e` step, no new run step needed.

- [ ] **Step 1: Guard against committing non-Linux baselines**

Append to `apps/web/.gitignore`:

```gitignore
# Visual-regression baselines are Linux-only (Docker-generated, see `just visual-update`).
# A dev's local-platform baseline must never be committed.
e2e/**/*-darwin.png
e2e/**/*-win32.png
```

- [ ] **Step 2: Upload the pixel diff/actual as a CI artifact on failure**

In `.github/workflows/ci.yml`, in the `web` job, add a step AFTER `- run: pnpm test:e2e` that uploads the Playwright results when the job fails (so a pixel diff is inspectable). Add:

```yaml
      - name: Upload Playwright results (visual diffs) on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-results
          path: apps/web/test-results/
          retention-days: 7
```

- [ ] **Step 3: Prove the gate CATCHES a real diff (then revert)**

This is the "failing test" for visual-regression — confirm the gate actually fails on an unintended change.
1. Temporarily edit a visible style, e.g. in `apps/web/src/app/globals.css` change `--accent: #2e7d4f;` to `--accent: #b3541e;`.
2. Run: `just visual`
   Expected: FAIL — at least the `jobs`/`jobs-cards`/`jobs-ring` snapshots differ (accent color shifted), Playwright reports the pixel diff.
3. **Revert the edit** (`git checkout apps/web/src/app/globals.css`).
4. Run: `just visual` again → PASS (11 passed).

Do NOT commit the temporary edit or any regenerated baseline from it. If a baseline got updated during the experiment, `git checkout apps/web/e2e/visual` to restore the committed ones.

- [ ] **Step 4: Confirm the full E2E suite is green (all projects)**

Run: `just visual` (Docker, the pixel gate) → PASS (11).
Then from `apps/web`, the behavioral suite still passes: `pnpm exec playwright test --project=public --project=authed` → PASS (the non-visual specs; these run natively, no Docker).
(`pnpm test:e2e` runs all three projects but the `visual` project needs the Linux/Docker renderer to match the committed baselines, so run the visual gate via `just visual` and the behavioral projects natively — CI runs all three on native Linux where they all match.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml apps/web/.gitignore
git commit -m "ci(web): upload visual diffs on failure + guard non-linux baselines (M1d-2)"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** Task 1 → §2 (visual project + fixture + `animations:disabled`) + §5 (Docker recipes) + one snapshot. Task 2 → §4 snapshots 1–9 (signin + 7 views + drawer). Task 3 → §4 snapshots 10–11 (cards, ring). Task 4 → §6 (CI gate + failure artifact) + §8 (darwin `.gitignore` guard + prove-the-gate). Determinism harness (§2) is the shared fixture used by every snapshot.
- **Snapshot naming:** Playwright names snapshots `<name>-<project>-<platform>.png` → `jobs-chromium-linux.png` etc., stored in `<specfile>-snapshots/`. The committed baselines are the `-chromium-linux.png` variants; CI (chromium on linux) matches them.
- **TDD adaptation:** snapshot tests have no code-level red→green; the "gate catches a diff" proof (Task 4 Step 3) is the equivalent failing-test check, run once at the end. Each snapshot task's real gate is `just visual` passing against the just-eyeballed baselines.
- **CONTROLLER-VERIFIED baselines:** the eyeball steps (1.6, 2.3, 3.3) are not automatable — a reviewer can't judge a binary PNG from a diff. Whoever executes MUST open each generated PNG and confirm it's a correct render before committing; the task reviewer verifies the spec/config/fixture code + that baselines exist + are `-linux.png`, and defers baseline *correctness* to that eyeball.
- **Docker note:** the recipe mounts the whole repo (pnpm workspace) + masks root/apps-web/shared-types `node_modules` with anonymous volumes (so host darwin binaries don't leak) + runs Playwright's own dev server inside the container (no `--network host` needed). Docker daemon confirmed reachable.
- **No product code changes** — every task is additive test infra; the only `src/` touch is the temporary-then-reverted accent edit in Task 4 Step 3.
