# Specula M1d-2 — Pixel visual-regression: Design Spec

> **Status:** approved design, ready for `writing-plans`.
> **Milestone:** M1d-2 — the second of two M1d sub-pieces (M1d = "Tweaks panel + visual-regression").
> M1d-1 (the Tweaks panel) ✅ → **M1d-2 (pixel visual-regression)**. **This completes M1.** After M1:
> M2 = real FastAPI + persistence.
> **Sources of truth:** the built app (the 8 views + drawer + Tweaks from M1a–M1d-1), the existing
> Playwright harness (`apps/web/playwright.config.ts`, two-server), the CI e2e job
> (`.github/workflows/ci.yml`), `CLAUDE.md`.
> **This is test infrastructure**, not a product feature — no user-facing change.

---

## 1. Goal & boundary

Lock the pixel-faithful design port with **deterministic screenshot regression tests**: a Playwright
`toHaveScreenshot` suite that snapshots the key views + drawer + the M1d-1 tweaked states, compared
against **Linux baselines** committed to the repo (generated in the pinned Playwright Docker image so
they match CI's renderer), gated in CI so an unintended visual change fails the build.

**In scope (M1d-2):**
1. A separate **`visual` Playwright project** (`e2e/visual/`) with its own screenshot config
   (`animations: "disabled"`, a small pixel-diff tolerance), served by the existing `:3001` bypass
   server (which serves *all* routes including `/signin`).
2. A **determinism harness** (a shared fixture/helper) so every snapshot is byte-stable: skip the
   intro, emulate reduced-motion, wait for fonts + network-idle before shooting.
3. The **snapshot suite** (~11 states — §4).
4. **`just visual-update`** — a recipe that regenerates the Linux baselines inside the pinned
   Playwright Docker image; the baselines are committed under `e2e/visual/`.
5. **CI gate** — the existing `pnpm test:e2e` runs the `visual` project on CI's native Linux;
   an unexpected diff fails the build and uploads the actual/diff PNGs as artifacts.

**Out of scope (deferred, with owner):**
- **Snapshotting every tweak permutation** (all accents/fonts/densities) — YAGNI; the ~11 set covers
  the port + drawer + the two structurally-distinct tweaked states (cards, ring). Add more only if a
  real regression escapes.
- **Cross-browser / responsive snapshots** (Firefox/WebKit, mobile viewports) — the app is
  desktop-first Chromium (spec §14); single-viewport Chromium is the target.
- **Component-level (Storybook-style) snapshots** — not adopting Storybook; page-level Playwright
  snapshots are the mechanism.
- Product behavior changes — none. M2 (real API) may shift rendered data later; baselines get
  regenerated then via the same recipe (the seed still renders the same in M1).

**Invariants honored** (`CLAUDE.md`): no product code changes; the visual suite is additive test
infra. It runs on the dev-only bypass server (`NODE_ENV !== "production"` gate intact) — never a prod
build.

---

## 2. Architecture

- **Why a separate `visual` project (not folded into `authed`):** pixel comparison is slower and has
  its own tolerance/config; keeping it a distinct Playwright project (a) lets the fast behavioral E2E
  stay decoupled, (b) gives the screenshot config one home, and (c) lets CI/devs run
  `--project=visual` alone. It matches `e2e/visual/` and uses `baseURL: http://localhost:3001`
  (the bypass server already in the config — it renders every route, `/signin` included, so one
  project covers public + app views).
- **Determinism is the whole game.** Pixel tests fail on any non-determinism. The harness pins every
  source:
  - **Animations:** `toHaveScreenshot({ animations: "disabled" })` — Playwright freezes CSS
    animations/transitions to their *end state* and fast-forwards Web Animations. This turns the M1c
    entrances/FLIP/reveal/morph into stable end-frames.
  - **Reduced-motion:** `page.emulateMedia({ reducedMotion: "reduce" })` — belt-and-suspenders; the
    count-ups (intro/insights/meters) then render final values, not mid-count.
  - **Intro:** `sessionStorage.setItem("specula_intro","1")` via `addInitScript` so the overlay never
    covers a view.
  - **Fonts:** `await page.evaluate(() => document.fonts.ready)` + `waitForLoadState("networkidle")`
    before shooting — next/font is self-hosted (no network flakiness), but fonts-ready guarantees the
    serif faces are painted.
  - **Data:** the seed is static; **no live dates** are rendered (the "posted"/"added" strings are
    seed constants), so content is inherently stable.
  - **Scrollbars/viewport:** a fixed viewport (1440×900) set on the project; `fullPage: true` for the
    scrolling views so the whole view is captured deterministically.
- **Baselines are Linux, committed, Docker-generated.** Playwright names snapshots with a platform
  suffix (`*-linux.png`). Baselines are generated on Linux (via the pinned Playwright Docker image so
  the Chromium build + font stack match CI exactly) and committed under `e2e/visual/`. CI's native
  Linux Chromium compares against them. macOS dev machines never generate the committed baselines
  (a `*-darwin.png` would just be ignored by CI) — the `just visual-update` recipe is the only
  sanctioned way to (re)generate them.

---

## 3. Files

```
apps/web/
  e2e/visual/
    fixtures.ts                 # CREATE — the determinism fixture (stablepage: intro-skip + reduced-motion + fonts-ready)
    views.spec.ts               # CREATE — signin + 7 app views + drawer snapshots
    tweaks.spec.ts              # CREATE — the 2 tweaked-state snapshots (cards, ring)
    views.spec.ts-snapshots/    # CREATE (committed) — the *-linux.png baselines (Docker-generated)
    tweaks.spec.ts-snapshots/   # CREATE (committed) — "
  playwright.config.ts          # MODIFY — add the `visual` project (matches e2e/visual/, :3001, screenshot config)
justfile                        # MODIFY — add `visual-update` (Docker) + `visual` (local run) recipes
.github/workflows/ci.yml        # MODIFY — on visual failure, upload the diff/actual PNGs as an artifact
```

`fixtures.ts` isolates the determinism harness so both spec files (and any future one) share one
stable-page setup — DRY, and the single place to tune stabilization.

---

## 4. The snapshot set (~11 — focused + complete)

Each is one `await expect(page).toHaveScreenshot("<name>.png", { fullPage: true })` after the harness
stabilizes the page.

**`views.spec.ts`** (default states — locks the pixel-faithful port):
1. `signin.png` — the sign-in page (public route, on :3001).
2. `jobs.png` — the Jobs view (lens bar, rows, meters, banner).
3. `jobs-drawer.png` — the Jobs view with a row's Drawer open (all sections; morph settled to
   end-state via `animations: "disabled"`).
4. `approvals.png` — the Approval queue (cards).
5. `companies.png` — the Companies registry (table).
6. `insights.png` — the Insights dashboard (six chart panels).
7. `profiles.png` — Search profiles (lens cards).
8. `candidate.png` — Candidate profile (form + skills-gap).
9. `targeting.png` — Targeting (tag fields + banner).

**`tweaks.spec.ts`** (locks the M1d-1 wiring that would otherwise silently regress):
10. `jobs-cards.png` — Jobs with `layout=cards` (2-col card grid; set via `localStorage` init script,
    not by clicking, for determinism).
11. `jobs-ring.png` — Jobs with `mstyle=ring` (conic-ring meters).

> Rationale for the breadth: the 8 views + drawer cover the whole port; the 2 tweaked states cover the
> structurally-distinct Tweaks output (a new grid layout; a new meter render). Accent/font/density
> changes are single-property CSS swaps already unit-covered by `applyTweaks` — snapshotting them adds
> maintenance (11→dozens of baselines) for little marginal catch. Add more only if a regression escapes.

---

## 5. Baseline generation (`just visual-update` — Docker)

```
# regenerate the committed Linux baselines in the pinned Playwright image (matches CI's renderer)
visual-update:
    docker run --rm --network host -v {{justfile_directory()}}/apps/web:/work -w /work \
      mcr.microsoft.com/playwright:v1.61.1-noble \
      sh -c "corepack enable && pnpm install --frozen-lockfile && pnpm exec playwright test --project=visual --update-snapshots"

# run the visual suite locally against the pinned image (compare only — no update)
visual:
    docker run --rm --network host -v {{justfile_directory()}}/apps/web:/work -w /work \
      mcr.microsoft.com/playwright:v1.61.1-noble \
      sh -c "corepack enable && pnpm install --frozen-lockfile && pnpm exec playwright test --project=visual"
```

- The image tag **`v1.61.1-noble`** is pinned to `@playwright/test@1.61.1` (the installed version) and
  Ubuntu Noble (24.04) — the same Chromium + font stack CI's `ubuntu-latest` + `playwright install
  --with-deps` provides, so a Docker-generated baseline matches a CI-rendered actual.
- `--network host` lets the container reach the `:3001` dev server. The container runs Playwright's
  `webServer` itself (it starts `pnpm dev --port 3001`), so the recipe is self-contained — no separate
  server needed. (If host networking is unavailable on the platform, the fallback is running the dev
  server inside the container via the existing `webServer` config, which Playwright already does.)
- After running, the dev **reviews the changed `*-linux.png`** in the diff and commits them. A baseline
  change is a deliberate, reviewable act — never auto-committed.
- **The `just visual-update` recipe is bumped whenever `@playwright/test` is upgraded** (the tag must
  track the version). A one-line note in the recipe comment says so.

---

## 6. CI gate

- The existing `- run: pnpm test:e2e` already runs **all** projects → the `visual` project runs on CI
  (native Ubuntu + the `playwright install --with-deps chromium` already in the job). No new step to
  run them; they gate the build.
- **On failure**, add an `if: failure()` step uploading `apps/web/test-results/` (Playwright writes the
  actual + diff PNGs there) as a workflow artifact, so a pixel diff is inspectable without reproducing
  locally.
- **Tolerance:** the project config sets a small `maxDiffPixelRatio` (≈0.01) + `threshold` (≈0.2) so
  sub-pixel antialiasing noise doesn't flake the gate, while a real visual change (a moved element, a
  color shift, a broken layout) still trips it. Tuned during baseline bring-up.
- The committed baselines live in `e2e/visual/**-snapshots/` (NOT under the gitignored `test-results/`),
  so they're versioned; `test-results/` (actuals/diffs) stays ignored.

---

## 7. Testing & acceptance (M1d-2 definition of done)

This milestone *is* tests, so "testing" = the suite runs green against committed baselines.

1. `apps/web/e2e/visual/{views,tweaks}.spec.ts` snapshot the ~11 states via the shared determinism
   fixture; a `visual` Playwright project is configured (:3001, animations disabled, tolerance set).
2. **Linux baselines** for all ~11 snapshots are generated via `just visual-update` (the pinned
   Docker image) and **committed** under `e2e/visual/`.
3. `just visual` (Docker, compare-only) passes locally against the committed baselines.
4. **CI green:** `pnpm test:e2e` (public + authed + **visual**) passes on CI; the failure-artifact
   upload step is present.
5. A deliberate visual change (verified during bring-up: temporarily tweak a color) **fails** the
   `visual` project (proving the gate works), then revert.
6. `just lint && just typecheck` + `pre-commit run --all-files` green (the fixture/specs are TS-strict);
   no product code changed.

---

## 8. Open considerations for the plan
- **Bring-up order:** write the config + fixture + specs first, run `just visual-update` to mint the
  baselines, eyeball each PNG (they're the source of truth — a wrong baseline locks in a wrong render),
  then commit. The plan's final task verifies the gate catches a deliberate diff.
- **The `jobs-drawer` snapshot** must open the drawer deterministically — click a specific row (stable
  first row) or deep-render; with `animations: "disabled"` the morph is already frozen to end-state.
- **`fullPage` vs viewport:** use `fullPage: true` so a view taller than the viewport is fully captured
  (Insights/Candidate are tall); the fixed viewport width (1440) keeps layout deterministic.
- **Docker `--network host`** is Linux-native; on macOS Docker Desktop it also works for reaching a
  container-internal server since Playwright starts its own `webServer` inside the container — the
  recipe doesn't depend on reaching the *host's* :3001.
- **Baseline hygiene:** only `*-linux.png` are committed; add a `.gitignore` guard for `*-darwin.png`/
  `*-win32.png` so a dev's accidental local-platform baseline never lands.
- Everything else is specified; no TBDs.
