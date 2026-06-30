# Specula M0a — Web Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the create-next-app boilerplate in `apps/web` with Specula's editorial-instrument shell — design tokens, fonts, sidebar, and seven routed views as empty placeholders — so the app *looks like Specula* and every screen is reachable, with no data, no backend, and none of the signature animations.

**Architecture:** A Next.js 16 App Router app. Design tokens from the prototype become the Tailwind v4 `@theme`; the runtime-swappable subset (`--accent` + derived, density) lives as `:root` CSS variables. A `(app)` route group wraps a grid shell (`236px 1fr`) with a fixed `Sidebar` (client component, active state via `usePathname`) and a scrolling main column. Seven `page.tsx` files render a shared `ViewShell` chrome + an "arrives in M1" empty state. Tested with Vitest+RTL (fast component/logic) and Playwright (browser E2E).

**Tech Stack:** Next.js 16.2.9 · React 19 · TypeScript (strict) · Tailwind CSS v4 (`@theme`, CSS-first) · `next/font/google` · Vitest + Testing Library + jsdom · Playwright · pnpm.

## Global Constraints

Apply to **every** task. Sources: `docs/superpowers/specs/2026-06-30-m0a-web-shell-design.md`, `docs/Specula - Design Spec.md` §10–§11, `docs/Specula - Design Spec (prototype).md` §2/§6, `CLAUDE.md`.

- **Working directory:** `apps/web` unless a path says otherwise; repo root is `/Users/jorisrombouts/Projects/Personal/specula`. Run web commands from `apps/web` (or `just …` from root).
- **Pixel values are canonical from `prototype/specula/specula.css`** — every number in this plan was copied from it; do not round or "improve" them. Visuals → prototype wins; architecture/behavior → production spec wins.
- **Styling = Tailwind-native rebuild.** Build with Tailwind v4 utilities + tokens-as-theme. Do **not** port `specula.css` verbatim (except the two small CSS rules this plan specifies: the `:root`/density vars and the webkit scrollbar). M1 adds visual-regression; M0a tests assert structure + the paper background, not pixel diffs.
- **No fabricated data.** No hard-coded counts, no fake "synced 2d ago", no invented candidate name. Count badges render **only when a count prop is supplied** (none is, in M0a). Sync row + Refresh button + candidate card are visibly **inert placeholders**. This enforces the spec invariant "counts are DERIVED server-side, never stored/hard-coded."
- **Scope is the shell only.** No seed data, no Jobs/Drawer/MatchMeter content, no Tweaks panel UI, no signature animations, no auth/DB. Those are M1/M0b. Build nothing speculative (YAGNI).
- **Next.js 16** (the approved override of the spec's "15"), TS strict stays on, the Phase-0 quality gates stay green: `pnpm lint`, `pnpm typecheck`, `pnpm format:check`, `pnpm build`.
- **Two test runners, scoped so they don't collide:** Vitest runs only `src/**/*.test.{ts,tsx}`; Playwright runs only `e2e/**`. Unit/component tests are named `*.test.tsx`; E2E specs live under `e2e/` and are named `*.spec.ts`.
- **Active nav item** uses `aria-current="page"` (a11y + a stable test hook) in addition to its visual `.on` styling.
- **Pre-commit hooks are installed** (from Phase 0). Commits touching `apps/web/**` trigger `pnpm lint && pnpm format:check`; commits touching `apps/api/**` trigger ruff/mypy. Keep new files lint- and Prettier-clean so commits don't bounce.

---

## File Structure

```
apps/web/
  package.json                      # MODIFY (Task 1,2) — add test deps + scripts
  vitest.config.ts                  # CREATE (Task 1)
  vitest.setup.ts                   # CREATE (Task 1)
  playwright.config.ts              # CREATE (Task 1)
  README.md                         # DELETE boilerplate / replace (Task 2)
  src/
    app/
      globals.css                   # REPLACE (Task 2) — token theme + base + scrollbar
      layout.tsx                    # MODIFY (Task 2) — 5 fonts, paper body, drop Geist/dark-mode
      page.tsx                      # REPLACE (Task 3) — redirect("/jobs")
      (app)/
        layout.tsx                  # CREATE (Task 3) — grid shell: <Sidebar/> + <main>
        jobs/page.tsx               # CREATE (Task 3)
        approvals/page.tsx          # CREATE (Task 3)
        companies/page.tsx          # CREATE (Task 3)
        insights/page.tsx           # CREATE (Task 3)
        profiles/page.tsx           # CREATE (Task 3)
        targeting/page.tsx          # CREATE (Task 3)
        candidate/page.tsx          # CREATE (Task 3)
    components/
      view-shell.tsx                # CREATE (Task 3)
      icon.tsx                      # CREATE (Task 4)
      sidebar.tsx                   # CREATE (Task 4)
      sidebar.test.tsx              # CREATE (Task 4)
    lib/
      nav.ts                        # CREATE (Task 1)
      nav.test.ts                   # CREATE (Task 1)
  e2e/
    shell.spec.ts                   # CREATE (Task 2 first case, grown in Task 3/4)
.github/workflows/ci.yml            # MODIFY (Task 5)
justfile                            # MODIFY (Task 5)
```

---

### Task 1: Test harnesses + nav model (TDD)

Sets up both test runners and builds the one piece of pure logic in M0a — the nav model and its active-state helper — test-first. No UI yet.

**Files:**
- Create: `apps/web/vitest.config.ts`, `apps/web/vitest.setup.ts`, `apps/web/playwright.config.ts`, `apps/web/src/lib/nav.ts`, `apps/web/src/lib/nav.test.ts`
- Modify: `apps/web/package.json` (dev deps + `test`, `test:e2e` scripts)

**Interfaces:**
- Produces: `NAV: NavEntry[]` and `isActive(href: string, pathname: string): boolean` from `@/lib/nav`; the `NavItem`/`NavSection`/`NavEntry`/`IconName` types. Consumed by `Sidebar` (Task 4).
- Produces: runnable `pnpm test` (Vitest, `src/**` only) and `pnpm test:e2e` (Playwright, `e2e/**` only).

- [ ] **Step 1: Install test dependencies**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm add -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom jsdom @playwright/test
```
Expected: deps added to `devDependencies`; `pnpm-lock.yaml` updated.

- [ ] **Step 2: Add test scripts to `package.json`**

In `apps/web/package.json` `"scripts"`, add (keep all existing scripts):
```json
{
  "test": "vitest run",
  "test:e2e": "playwright test"
}
```

- [ ] **Step 3: Write Vitest config (scoped to `src/**`) + setup**

`apps/web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
```
`apps/web/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Write Playwright config (scoped to `e2e/**`)**

`apps/web/playwright.config.ts`:
```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: "http://localhost:3000", trace: "on-first-retry" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
```

- [ ] **Step 5: Write the failing test for the nav model**

`apps/web/src/lib/nav.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { NAV, isActive, type NavItem } from "@/lib/nav";

const items = NAV.filter((e): e is NavItem => "id" in e);

describe("NAV model", () => {
  it("has the six sidebar nav items in order", () => {
    expect(items.map((i) => i.id)).toEqual([
      "jobs",
      "approvals",
      "companies",
      "insights",
      "profiles",
      "targeting",
    ]);
  });

  it("groups items under the three section labels", () => {
    expect(NAV.filter((e) => "section" in e).map((e) => (e as { section: string }).section)).toEqual([
      "Pipeline",
      "Intelligence",
      "Configure",
    ]);
  });

  it("maps each item to its own route", () => {
    expect(items.map((i) => i.href)).toEqual([
      "/jobs",
      "/approvals",
      "/companies",
      "/insights",
      "/profiles",
      "/targeting",
    ]);
  });
});

describe("isActive", () => {
  it("matches the exact route", () => {
    expect(isActive("/jobs", "/jobs")).toBe(true);
  });
  it("does not match a different route", () => {
    expect(isActive("/jobs", "/companies")).toBe(false);
  });
  it("matches nested paths under the route", () => {
    expect(isActive("/jobs", "/jobs/abc")).toBe(true);
  });
});
```

- [ ] **Step 6: Run the test to verify it fails**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test
```
Expected: FAIL — `Failed to resolve import "@/lib/nav"` (module does not exist yet).

- [ ] **Step 7: Implement `lib/nav.ts`**

`apps/web/src/lib/nav.ts`:
```ts
export type IconName =
  | "jobs"
  | "approvals"
  | "companies"
  | "insights"
  | "profiles"
  | "targeting"
  | "candidate";

export type NavItem = { id: string; label: string; href: string; icon: IconName };
export type NavSection = { section: string };
export type NavEntry = NavSection | NavItem;

export const NAV: NavEntry[] = [
  { section: "Pipeline" },
  { id: "jobs", label: "Jobs", href: "/jobs", icon: "jobs" },
  { id: "approvals", label: "Approval queue", href: "/approvals", icon: "approvals" },
  { id: "companies", label: "Companies", href: "/companies", icon: "companies" },
  { section: "Intelligence" },
  { id: "insights", label: "Insights", href: "/insights", icon: "insights" },
  { section: "Configure" },
  { id: "profiles", label: "Search profiles", href: "/profiles", icon: "profiles" },
  { id: "targeting", label: "Targeting", href: "/targeting", icon: "targeting" },
];

/** A nav item is active when the current pathname equals its href or is nested under it. */
export function isActive(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
```

- [ ] **Step 8: Run the test to verify it passes**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test
```
Expected: PASS — all six cases green.

- [ ] **Step 9: Verify the quality gates still pass**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm lint && pnpm typecheck && pnpm format:check
```
Expected: all green. If `format:check` flags the new files, run `pnpm format` then re-check.

- [ ] **Step 10: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web
git commit -m "test(web): add Vitest + Playwright harnesses and tested nav model"
```

---

### Task 2: Design tokens, fonts, and the paper background

Replace the create-next-app theme/fonts with Specula's tokens and fonts. First Playwright E2E proves the token system is live.

**Files:**
- Modify: `apps/web/src/app/globals.css` (full replace), `apps/web/src/app/layout.tsx` (full replace), `apps/web/README.md` (replace boilerplate)
- Create: `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- Consumes: nothing from Task 1 at runtime (independent).
- Produces: the `@theme` utilities (`bg-paper`, `text-ink`, `text-ink-2`, `border-rule`, `font-display`, `font-mono`, `shadow-pop`, …) and the `--font-spectral`/`--font-hanken`/`--font-geist-mono` CSS variables on `<html>`. Consumed by Tasks 3–4.

- [ ] **Step 1: Write the failing E2E test (paper background)**

`apps/web/e2e/shell.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

test("the app renders on warm paper", async ({ page }) => {
  await page.goto("/");
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  // --paper #FBFAF6 == rgb(251, 250, 246)
  expect(bg).toBe("rgb(251, 250, 246)");
});
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm exec playwright install chromium && pnpm test:e2e
```
Expected: FAIL — current body background is white (`rgb(255, 255, 255)`), not paper. (First run also installs the chromium browser.)

- [ ] **Step 3: Replace `globals.css` with the token theme**

`apps/web/src/app/globals.css` (entire file):
```css
@import "tailwindcss";

/* Runtime-swappable variables (the M1 Tweaks panel mutates these). */
:root {
  --accent: #2e7d4f;
  --accent-bg: #e7f0e9;
  --accent-ink: #1e5d39;
  /* density (driven by [data-density] on <html>; default = comfortable) */
  --row-py: 17px;
  --gutter: 34px;
  --card-pad: 20px;
}
[data-density="compact"] {
  --row-py: 11px;
  --gutter: 26px;
  --card-pad: 15px;
}

@theme {
  --color-paper: #fbfaf6;
  --color-panel: #f4f2eb;
  --color-panel-2: #eeebe1;
  --color-card: #ffffff;
  --color-ink: #211e18;
  --color-ink-2: #7c7567;
  --color-ink-3: #aba493;
  --color-rule: #e4e0d5;
  --color-rule-2: #d6d1c2;
  --color-accent: var(--accent);
  --color-accent-bg: var(--accent-bg);
  --color-accent-ink: var(--accent-ink);
  --color-warn: #b3541e;
  --color-warn-bg: #f7ebe0;
  --color-gold: #9a7a18;

  --font-display: var(--font-spectral), serif;
  --font-body: var(--font-hanken), sans-serif;
  --font-mono: var(--font-geist-mono), monospace;

  --shadow-card: 0 1px 2px rgba(33, 30, 24, 0.04);
  --shadow-pop:
    0 16px 50px -12px rgba(33, 30, 24, 0.28), 0 2px 8px rgba(33, 30, 24, 0.08);
}

@layer base {
  html {
    font-size: 14px;
  }
  body {
    font-family: var(--font-body);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }
  ::selection {
    background: var(--accent-bg);
  }
}

/* Main scroll column — webkit scrollbar (matches prototype .main) */
.main-scroll::-webkit-scrollbar {
  width: 10px;
}
.main-scroll::-webkit-scrollbar-thumb {
  background: var(--color-rule-2);
  border-radius: 10px;
  border: 3px solid var(--color-paper);
}
```

- [ ] **Step 4: Replace `layout.tsx` with the Specula fonts + paper body**

`apps/web/src/app/layout.tsx` (entire file):
```tsx
import type { Metadata } from "next";
import { Spectral, Hanken_Grotesk, Geist_Mono, Newsreader, Source_Serif_4 } from "next/font/google";
import "./globals.css";

// Spectral is NOT a variable font on Google Fonts — explicit weights are required.
const spectral = Spectral({
  variable: "--font-spectral",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
// Hanken Grotesk, Geist Mono, Newsreader, Source Serif 4 are variable fonts — omit weight.
const hanken = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
// Loaded for the M1 font Tweak; not applied to anything in M0a.
const newsreader = Newsreader({ variable: "--font-newsreader", subsets: ["latin"] });
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Specula",
  description: "Specula — role ledger",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${spectral.variable} ${hanken.variable} ${geistMono.variable} ${newsreader.variable} ${sourceSerif.variable}`}
    >
      <body className="bg-paper text-ink">{children}</body>
    </html>
  );
}
```

- [ ] **Step 5: Run the E2E test to verify it passes**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test:e2e
```
Expected: PASS — body background is now `rgb(251, 250, 246)`.

- [ ] **Step 6: Replace the create-next-app README boilerplate**

Replace `apps/web/README.md` (entire file):
```markdown
# Specula — web

The Next.js 16 (App Router, Tailwind v4) front end. See the repo root `README.md` for setup and
`docs/Specula - Design Spec.md` for architecture. Run from the repo root: `just dev-web`.
```

- [ ] **Step 7: Verify build + gates**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```
Expected: all green (the unused `hanken`/`geistMono`/`newsreader`/`sourceSerif` consts are referenced in `className`, so no unused-var lint error; `newsreader`/`sourceSerif` ARE referenced there too). If `format:check` flags files, run `pnpm format` and re-check.

- [ ] **Step 8: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web
git commit -m "feat(web): Specula design tokens, fonts, and paper shell base"
```

---

### Task 3: App shell grid + seven empty routes

The `(app)` route group, the grid shell with a minimal functional nav (full Sidebar comes in Task 4), the shared `ViewShell`, the seven empty views, and the `/`→`/jobs` redirect.

**Files:**
- Replace: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/(app)/layout.tsx`, `apps/web/src/components/view-shell.tsx`, and the seven `apps/web/src/app/(app)/<route>/page.tsx`
- Modify: `apps/web/e2e/shell.spec.ts` (add navigation cases)

**Interfaces:**
- Consumes: `NAV` from `@/lib/nav` (Task 1); the token utilities (Task 2).
- Produces: the seven routes, each rendering `<section data-screen-label="<id>">`; `ViewShell({ label, title, sub })`. The `(app)/layout.tsx` renders a temporary inline nav that Task 4 replaces with `<Sidebar/>`.

- [ ] **Step 1: Add failing E2E navigation cases**

Append to `apps/web/e2e/shell.spec.ts`:
```ts
const ROUTES = [
  { href: "/jobs", label: "jobs" },
  { href: "/approvals", label: "approvals" },
  { href: "/companies", label: "companies" },
  { href: "/insights", label: "insights" },
  { href: "/profiles", label: "profiles" },
  { href: "/targeting", label: "targeting" },
  { href: "/candidate", label: "candidate" },
];

test("/ redirects to /jobs", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.locator('[data-screen-label="jobs"]')).toBeVisible();
});

for (const route of ROUTES) {
  test(`renders the ${route.label} view at ${route.href}`, async ({ page }) => {
    await page.goto(route.href);
    await expect(page.locator(`[data-screen-label="${route.label}"]`)).toBeVisible();
  });
}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test:e2e
```
Expected: FAIL — `/` is still the Phase-0 placeholder; the routed views and `data-screen-label`s don't exist.

- [ ] **Step 3: Create the shared `ViewShell`**

`apps/web/src/components/view-shell.tsx`:
```tsx
export function ViewShell({
  label,
  title,
  sub,
}: {
  label: string;
  title: string;
  sub: string;
}) {
  return (
    <section data-screen-label={label} className="mx-auto max-w-[1180px] px-[34px] pb-16 pt-[30px]">
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            {title}
          </h1>
          <p className="max-w-[64ch] text-ink-2 text-[13.5px]">{sub}</p>
        </div>
      </header>
      <p className="font-mono mt-8 text-ink-3 text-[11px] uppercase tracking-[0.08em]">
        Arrives in M1
      </p>
    </section>
  );
}
```

- [ ] **Step 4: Create the seven empty route pages**

Create each file with exactly this content:

`apps/web/src/app/(app)/jobs/page.tsx`:
```tsx
import { ViewShell } from "@/components/view-shell";

export default function JobsPage() {
  return (
    <ViewShell
      label="jobs"
      title="Jobs"
      sub="The scored, deduplicated pool of roles. Arrives in M1."
    />
  );
}
```
`apps/web/src/app/(app)/approvals/page.tsx`:
```tsx
import { ViewShell } from "@/components/view-shell";

export default function ApprovalsPage() {
  return (
    <ViewShell
      label="approvals"
      title="Approval queue"
      sub="Candidate companies awaiting your decision. Arrives in M1."
    />
  );
}
```
`apps/web/src/app/(app)/companies/page.tsx`:
```tsx
import { ViewShell } from "@/components/view-shell";

export default function CompaniesPage() {
  return (
    <ViewShell
      label="companies"
      title="Companies"
      sub="Your registry of tracked companies. Arrives in M1."
    />
  );
}
```
`apps/web/src/app/(app)/insights/page.tsx`:
```tsx
import { ViewShell } from "@/components/view-shell";

export default function InsightsPage() {
  return (
    <ViewShell
      label="insights"
      title="Insights"
      sub="Personal market intelligence. Arrives in M1."
    />
  );
}
```
`apps/web/src/app/(app)/profiles/page.tsx`:
```tsx
import { ViewShell } from "@/components/view-shell";

export default function ProfilesPage() {
  return (
    <ViewShell
      label="profiles"
      title="Search profiles"
      sub="Lenses over the shared pool. Arrives in M1."
    />
  );
}
```
`apps/web/src/app/(app)/targeting/page.tsx`:
```tsx
import { ViewShell } from "@/components/view-shell";

export default function TargetingPage() {
  return (
    <ViewShell
      label="targeting"
      title="Targeting"
      sub="What you want — roles, must-haves, values. Arrives in M1."
    />
  );
}
```
`apps/web/src/app/(app)/candidate/page.tsx`:
```tsx
import { ViewShell } from "@/components/view-shell";

export default function CandidatePage() {
  return (
    <ViewShell
      label="candidate"
      title="Candidate"
      sub="Who you are — the profile that drives scoring. Arrives in M1."
    />
  );
}
```

- [ ] **Step 5: Create the `(app)` shell layout with a temporary inline nav**

`apps/web/src/app/(app)/layout.tsx`:
```tsx
import Link from "next/link";
import { NAV, type NavItem } from "@/lib/nav";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <aside className="flex flex-col overflow-hidden border-r border-rule bg-panel">
        <div className="border-b border-rule px-5 pb-4 pt-[22px]">
          <span className="font-display text-[23px] font-semibold tracking-[0.05em] text-ink">
            Specula
          </span>
        </div>
        <nav className="flex-1 overflow-y-auto p-[14px_12px]">
          {NAV.map((entry, i) =>
            "section" in entry ? (
              <div
                key={`s${i}`}
                className="font-mono px-[10px] pb-[7px] pt-[14px] text-[9.5px] uppercase tracking-[0.16em] text-ink-3"
              >
                {entry.section}
              </div>
            ) : (
              <Link
                key={(entry as NavItem).id}
                href={(entry as NavItem).href}
                className="flex items-center gap-[10px] rounded-lg px-[11px] py-[9px] text-[13.5px] font-medium text-ink-2 hover:bg-panel-2 hover:text-ink"
              >
                {(entry as NavItem).label}
              </Link>
            ),
          )}
        </nav>
      </aside>
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
}
```

- [ ] **Step 6: Replace the root `page.tsx` with a redirect**

`apps/web/src/app/page.tsx` (entire file):
```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/jobs");
}
```

- [ ] **Step 7: Run the E2E suite to verify it passes**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test:e2e
```
Expected: PASS — `/`→`/jobs` redirect works; all seven `data-screen-label`s render; the paper-bg test still passes.

- [ ] **Step 8: Verify build + gates**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```
Expected: all green (run `pnpm format` if needed). `pnpm build` lists the seven routes + `/`.

- [ ] **Step 9: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web
git commit -m "feat(web): app shell grid, seven empty routes, and /->/jobs redirect"
```

---

### Task 4: The Sidebar component

Replace the inline nav with the full ported Sidebar: grouped sections, icons, active highlight, inert sync/refresh, candidate-card placeholder — with a Vitest component test.

**Files:**
- Create: `apps/web/src/components/icon.tsx`, `apps/web/src/components/sidebar.tsx`, `apps/web/src/components/sidebar.test.tsx`
- Modify: `apps/web/src/app/(app)/layout.tsx` (use `<Sidebar/>`), `apps/web/e2e/shell.spec.ts` (add sidebar cases)

**Interfaces:**
- Consumes: `NAV`, `isActive`, `IconName`, `NavItem` from `@/lib/nav` (Task 1); the token utilities (Task 2).
- Produces: `<Sidebar/>` (client component) and `<Icon name={IconName} />`.

- [ ] **Step 1: Write the failing Sidebar component test**

`apps/web/src/components/sidebar.test.tsx`:
```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { Sidebar } from "@/components/sidebar";

afterEach(cleanup);

function mockPath(pathname: string) {
  vi.doMock("next/navigation", () => ({ usePathname: () => pathname }));
}

describe("Sidebar", () => {
  it("renders the brand, all six nav items, and the candidate card", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S />);
    expect(screen.getByText("Specula")).toBeInTheDocument();
    for (const label of [
      "Jobs",
      "Approval queue",
      "Companies",
      "Insights",
      "Search profiles",
      "Targeting",
    ]) {
      expect(screen.getByRole("link", { name: new RegExp(label, "i") })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: /candidate/i })).toBeInTheDocument();
  });

  it("marks exactly the current route active via aria-current", async () => {
    mockPath("/companies");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S />);
    const active = screen.getAllByRole("link").filter((el) => el.getAttribute("aria-current") === "page");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveAccessibleName(/companies/i);
  });

  it("fabricates no counts — renders no digit badges", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    const { container } = render(<S />);
    // No numeric count/badge text anywhere in the sidebar nav (counts are derived; none in M0a).
    expect(container.querySelector("nav")?.textContent).not.toMatch(/\d/);
  });

  it("renders the Refresh button as inert (disabled)", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S />);
    expect(screen.getByRole("button", { name: /refresh/i })).toBeDisabled();
  });
});
```
> Note: the test uses `vi.doMock` + dynamic `import()` so each case can set a different `usePathname` before the module loads. `vi.resetModules()` is implicit per dynamic import here because `doMock` is not hoisted.

Add `import { beforeEach } from "vitest";` and a `beforeEach(() => vi.resetModules());` at the top of the `describe` if cases interfere; include it preemptively:
```tsx
import { beforeEach } from "vitest";
beforeEach(() => vi.resetModules());
```

- [ ] **Step 2: Run it to verify failure**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test
```
Expected: FAIL — `Failed to resolve import "@/components/sidebar"`.

- [ ] **Step 3: Create the Icon component (exact prototype paths)**

`apps/web/src/components/icon.tsx`:
```tsx
import type { IconName } from "@/lib/nav";

const PATHS: Record<IconName, string> = {
  jobs: "M2 3h12M2 8h12M2 13h8",
  approvals: "M3 8l3.5 3.5L13 4",
  companies: "M2.5 14V5l5-2.5L12.5 5v9M5.5 8h0.5M5.5 11h0.5M9.5 8h0.5M9.5 11h0.5",
  insights: "M2 14V2M2 14h12M5 11l3-4 2 2 3-5",
  profiles: "M3 4h10M5 8h8M7 12h6",
  candidate: "M8 8.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM3 14c0-2.5 2.2-4 5-4s5 1.5 5 4",
  targeting: "M8 14A6 6 0 108 2a6 6 0 000 12zM8 11a3 3 0 100-6 3 3 0 000 6zM8 8h0.01",
};

export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-full w-full"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
```

- [ ] **Step 4: Create the Sidebar component**

`apps/web/src/components/sidebar.tsx`:
```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV, isActive, type NavItem } from "@/lib/nav";
import { Icon } from "@/components/icon";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col overflow-hidden border-r border-rule bg-panel">
      {/* Brand + inert sync/refresh */}
      <div className="border-b border-rule px-5 pb-4 pt-[22px]">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-[23px] font-semibold tracking-[0.05em] text-ink">
            Specula
          </span>
          <span className="font-mono text-[10px] tracking-[0.02em] text-ink-2">role ledger</span>
        </div>
        <div className="mt-[14px] flex flex-col gap-[9px]">
          <div className="font-mono flex items-center gap-2 text-[11px] text-ink-2">
            <span className="relative h-[7px] w-[7px] flex-shrink-0 rounded-full bg-accent" />
            synced <b className="font-semibold text-ink">—</b> ·{" "}
            <b className="font-semibold text-ink">—</b> new
          </div>
          <button
            type="button"
            disabled
            title="Available in a later milestone"
            className="font-body mt-1 flex w-full items-center justify-center gap-[7px] rounded-[7px] bg-ink px-3 py-[9px] text-[12.5px] font-semibold text-paper opacity-60"
          >
            <span aria-hidden>↻</span> Refresh now
          </button>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-[14px_12px]">
        {NAV.map((entry, i) =>
          "section" in entry ? (
            <div
              key={`s${i}`}
              className="font-mono px-[10px] pb-[7px] pt-[14px] text-[9.5px] uppercase tracking-[0.16em] text-ink-3"
            >
              {entry.section}
            </div>
          ) : (
            <NavLink key={(entry as NavItem).id} item={entry as NavItem} pathname={pathname} />
          ),
        )}
      </nav>

      {/* Candidate card — neutral placeholder until M0b/M2 */}
      <div className="border-t border-rule p-3">
        <Link
          href="/candidate"
          aria-current={isActive("/candidate", pathname) ? "page" : undefined}
          className={`flex w-full items-center gap-[11px] rounded-[9px] border px-[10px] py-[9px] text-left ${
            isActive("/candidate", pathname)
              ? "border-rule bg-panel-2"
              : "border-transparent hover:border-rule hover:bg-panel-2"
          }`}
        >
          <span className="font-mono flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-[9px] bg-ink text-[13px] font-semibold text-paper">
            <span className="h-[15px] w-[15px]">
              <Icon name="candidate" />
            </span>
          </span>
          <span>
            <span className="block text-[13px] font-semibold text-ink">Candidate</span>
            <span className="block text-[11.5px] text-ink-2">profile</span>
          </span>
        </Link>
      </div>
    </aside>
  );
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const on = isActive(item.href, pathname);
  return (
    <Link
      href={item.href}
      aria-current={on ? "page" : undefined}
      className={`flex items-center gap-[10px] rounded-lg px-[11px] py-[9px] text-[13.5px] font-medium ${
        on ? "bg-ink text-paper" : "text-ink-2 hover:bg-panel-2 hover:text-ink"
      }`}
    >
      <span className="flex h-[15px] w-[15px] flex-shrink-0">
        <Icon name={item.icon} />
      </span>
      <span className="flex-1">{item.label}</span>
    </Link>
  );
}
```

- [ ] **Step 5: Use `<Sidebar/>` in the shell layout**

Replace `apps/web/src/app/(app)/layout.tsx` (entire file):
```tsx
import { Sidebar } from "@/components/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <Sidebar />
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
}
```

- [ ] **Step 6: Run the component test to verify it passes**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test
```
Expected: PASS — brand + nav + candidate render; exactly one `aria-current`; no digit badges; Refresh disabled. (Nav model tests from Task 1 still pass.)

- [ ] **Step 7: Add + run the E2E sidebar cases**

Append to `apps/web/e2e/shell.spec.ts`:
```ts
test("the sidebar shows the brand and grouped sections", async ({ page }) => {
  await page.goto("/jobs");
  await expect(page.getByText("Specula")).toBeVisible();
  for (const section of ["Pipeline", "Intelligence", "Configure"]) {
    await expect(page.getByText(section, { exact: true })).toBeVisible();
  }
});

test("the active nav item reflects the current route", async ({ page }) => {
  await page.goto("/companies");
  await expect(page.getByRole("link", { name: /Companies/i })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("link", { name: /^Jobs$/i })).not.toHaveAttribute("aria-current", "page");
});
```
Run:
```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test:e2e
```
Expected: PASS — all E2E cases green.

- [ ] **Step 8: Verify build + gates**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```
Expected: all green (run `pnpm format` if needed).

- [ ] **Step 9: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web
git commit -m "feat(web): editorial sidebar with active state, icons, and inert placeholders"
```

---

### Task 5: Wire web tests into CI and the justfile

Make the new tests run in CI and via `just`, resolving the Phase-0 "test both apps" comment.

**Files:**
- Modify: `.github/workflows/ci.yml`, `justfile`

**Interfaces:**
- Consumes: `pnpm test` (Vitest) and `pnpm test:e2e` (Playwright) from Task 1; both green from Tasks 2–4.

- [ ] **Step 1: Add Vitest + Playwright steps to the web CI job**

In `.github/workflows/ci.yml`, in the `web` job, **after** the existing `- run: pnpm build` step, add:
```yaml
      - run: pnpm test
      - run: pnpm exec playwright install --with-deps chromium
      - run: pnpm test:e2e
```
(The `web` job already has `defaults.run.working-directory: apps/web`, so no path prefix is needed.)

- [ ] **Step 2: Update the justfile `test` recipe + add `e2e`**

In `justfile`, replace the `test` recipe and add an `e2e` recipe:
```just
# Test both apps (api: pytest, web: vitest)
test:
    cd apps/api && uv run pytest
    cd apps/web && pnpm test

# Browser E2E for the web app (Playwright)
e2e:
    cd apps/web && pnpm test:e2e
```

- [ ] **Step 3: Verify the recipes locally**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
just test
just e2e
```
Expected: `just test` runs pytest (1 passed) **and** web Vitest (all green); `just e2e` runs Playwright (all green).

- [ ] **Step 4: Validate the CI YAML**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
pre-commit run check-yaml --files .github/workflows/ci.yml
```
Expected: `check-yaml` passes.

- [ ] **Step 5: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add .github/workflows/ci.yml justfile
git commit -m "ci: run web Vitest + Playwright; justfile test covers both apps"
```

- [ ] **Step 6: Push and confirm CI is green**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git push
gh run watch "$(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```
Expected: both CI jobs (`api`, `web`) succeed, web now including Vitest + Playwright.

---

## Self-Review

**1. Spec coverage** (design spec §1–§9):
- §1.1 tokens → Task 2 `globals.css`. §1.2 fonts → Task 2 `layout.tsx` (5 fonts; Newsreader/Source Serif loaded). §1.3 shell grid → Task 3 `(app)/layout.tsx`. §1.4 sidebar (brand, sync/refresh inert, grouped nav, active, candidate card) → Task 4. §1.5 seven empty routes + `data-screen-label` + `/`→`/jobs` → Task 3. §1.6 tests → Tasks 1–4 (Vitest + Playwright) + Task 5 (CI/justfile).
- Invariant "no fabricated counts" → Task 4 sidebar (em-dash placeholders, badges only when supplied) + the Vitest "no digit badges" case. Inert Refresh → disabled button + test. Candidate neutral placeholder → Task 4.
- Out-of-scope items (Tweaks panel, signature moments, seed data, auth) → correctly absent.
- §3 cleanup (Geist tokens, `apps/web/README.md` boilerplate, demo `page.tsx`) → Tasks 2–3.
- Acceptance §9: items 1–7 map to Task 3 (routes/redirect/scroll), Task 2 (paper/fonts), Task 4 (active highlight/no-fabrication), Tasks 1–5 (gates+tests+CI), Tasks 2–3 (cruft gone). **All covered.**

**2. Placeholder scan:** No "TBD"/"add error handling"/"write tests for the above". Every code step shows full file content or an exact append anchored to a named line. The seven near-identical pages are each written out in full (not "similar to"). The "Arrives in M1" string in the views is intentional product copy, not a plan placeholder.

**3. Type consistency:** `NavEntry`/`NavItem`/`NavSection`/`IconName` defined in Task 1 `lib/nav.ts` are the exact names imported in Task 3 (`(app)/layout.tsx`), Task 4 (`sidebar.tsx`, `icon.tsx`). `isActive(href, pathname)` signature is consistent across `nav.ts`, the Sidebar, and both test files. `ViewShell({label,title,sub})` defined in Task 3 matches all seven page call-sites. `Icon({name: IconName})` defined Task 4, consumed in Sidebar. The `IconName` union (7 keys incl. `candidate`) matches `PATHS` keys exactly. **Consistent.**
