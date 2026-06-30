# Specula M0a — Web Shell: Design Spec

> **Status:** approved design, ready for `writing-plans`.
> **Milestone:** M0a (first half of spec §18 "M0 — Foundations"). M0b (Auth.js + SQLAlchemy/Alembic
> + first migration + multi-tenancy) is a separate later cycle.
> **Sources of truth:** `docs/Specula - Design Spec.md` §10–§11, §18 (architecture/tokens/milestones);
> `docs/Specula - Design Spec (prototype).md` §2, §6, §11 (tokens, shell, build order); the prototype
> itself — `prototype/specula/app.jsx` (shell structure) and `prototype/specula/specula.css` (exact
> values). **Conflict rule:** visuals → prototype wins; architecture/behavior → production spec wins.

---

## 1. Goal & boundary

Replace the create-next-app boilerplate in `apps/web` with Specula's **editorial-instrument shell**:
the design tokens, the fonts, the sidebar, the layout grid, and the seven routed views as **empty
placeholders**. After M0a, the app *looks like Specula* and every screen is reachable — but there is
no data, no backend, and none of the four signature moments yet.

**In scope (M0a):**
1. **Design tokens** — the prototype's §2 palette/shadows/typography/density as the Tailwind v4 theme,
   with the runtime-swappable subset kept as `:root` CSS variables.
2. **Fonts** — Spectral, Hanken Grotesk, Geist Mono wired and applied via `next/font`; Newsreader +
   Source Serif 4 loaded (for M1's font Tweak) but not yet selectable.
3. **App shell** — `(app)/layout.tsx`: the `236px 1fr` grid, fixed sidebar + scrolling main column.
4. **Sidebar** — brand lockup, sync row (inert placeholder), Refresh button (inert placeholder),
   grouped nav with ported icons + active highlight, candidate card (neutral placeholder).
5. **Seven empty routes** under `(app)` — each with view-header chrome, an "arrives in M1" empty
   state, and a `data-screen-label` root attribute.
6. **Tests** — Playwright smoke (shell + navigation + active highlight + paper background) and a
   Sidebar component test.

**Out of scope (deferred, with the milestone that owns it):**
- Seed data, the Jobs list / Drawer / MatchMeter / all real view content → **M1**.
- The four signature moments (assembling intro, FLIP re-sort, scoring reveal, row→drawer morph) → **M1**.
- The **Tweaks panel UI** (its 5 controls) → **M1**. *M0a only makes the token system tweakable
  (the `:root` swap-targets exist); it builds no panel.*
- Real sidebar counts, real "synced Nd ago · N new", real candidate identity → **M2** (data) / **M3**
  (run status). M0a renders these as static, clearly-inert placeholders.
- Auth.js, login, user bootstrap, DB, migrations, tenancy → **M0b**.

**Invariants honored** (from `CLAUDE.md` / spec §19): **counts are derived, never hard-coded** — so in
a no-backend shell the nav count badges render **only when a count prop is supplied**, and none is
supplied in M0a (they wire to derived counts in M1/M2). Nothing fakes a number. Salary/scoring
invariants are not touched in M0a. Deviations stand: **no billing, no object storage.**

---

## 2. Styling approach (decided): Tailwind-native rebuild

The shell, sidebar, and shared atoms are **rebuilt with Tailwind v4 utility classes**, with the
prototype tokens as the theme — **not** a verbatim port of `specula.css`. The prototype's CSS is the
**reference for exact values** (every number in §4 below is copied from `specula.css`), but the
output is idiomatic Tailwind. M1 adds the visual-regression suite that guards against pixel drift;
M0a's own tests assert structure + the paper background, not pixel diffs.

Rationale: most maintainable as the app grows; the spec (§11) intends tokens-as-theme + utilities.
Risk (pixel drift) is accepted and mitigated by M1's visual-regression gate.

---

## 3. File structure

```
apps/web/src/
  app/
    layout.tsx              # MODIFY — root layout: load next/font, set <html> font vars + lang,
                            #   <body class="bg-paper text-ink ..."> ; metadata already "Specula"
    globals.css             # REPLACE — Tailwind v4 @import + @theme tokens + :root tweakable vars
                            #   + base typography/density rules. (Removes the Geist demo tokens.)
    page.tsx                # DELETE the placeholder; root "/" redirects to "/jobs" (see §6)
    (app)/
      layout.tsx            # CREATE — the grid shell: <Sidebar/> + <main> scroll column
      jobs/page.tsx         # CREATE — empty view (default screen)
      approvals/page.tsx    # CREATE — empty view
      companies/page.tsx    # CREATE — empty view
      insights/page.tsx     # CREATE — empty view
      profiles/page.tsx     # CREATE — empty view
      targeting/page.tsx    # CREATE — empty view
      candidate/page.tsx    # CREATE — empty view
  components/
    sidebar.tsx             # CREATE — client component (uses usePathname for active state)
    icon.tsx                # CREATE — inline-SVG icon set (ported from prototype ui.jsx Icon)
    view-shell.tsx          # CREATE — <ViewShell label title sub> chrome for empty views (DRY)
  lib/
    nav.ts                  # CREATE — the NAV model (sections + items: id, label, href, icon)
e2e/
  shell.spec.ts             # CREATE — Playwright smoke test
```

Notes:
- `apps/web/public/*.svg` were already removed in Phase 0. `apps/web/README.md` boilerplate and the
  Geist font tokens are removed as part of this milestone (the Phase-0-deferred cleanup lands here).
- No new top-level dirs beyond `components/`, `lib/`, `e2e/` — each holds ≥2 files or is the
  conventional home for its kind (the "≥2 files" rule; `e2e/` is the standard Playwright location).

---

## 4. Design tokens & fonts (exact values from `specula.css`)

### 4.1 `globals.css` structure

```css
@import "tailwindcss";

@theme {
  /* colors — names mirror the prototype CSS variables 1:1 */
  --color-paper: #FBFAF6;
  --color-panel: #F4F2EB;
  --color-panel-2: #EEEBE1;
  --color-card: #FFFFFF;
  --color-ink: #211E18;
  --color-ink-2: #7C7567;
  --color-ink-3: #ABA493;
  --color-rule: #E4E0D5;
  --color-rule-2: #D6D1C2;
  --color-accent: var(--accent);          /* live var so the Tweak can swap it (M1) */
  --color-accent-bg: var(--accent-bg);
  --color-accent-ink: var(--accent-ink);
  --color-warn: #B3541E;
  --color-warn-bg: #F7EBE0;
  --color-gold: #9A7A18;

  /* fonts — bound to next/font CSS variables (see §4.3) */
  --font-display: var(--font-spectral), serif;
  --font-body: var(--font-hanken), sans-serif;
  --font-mono: var(--font-geist-mono), monospace;

  --shadow-card: 0 1px 2px rgba(33,30,24,.04);
  --shadow-pop: 0 16px 50px -12px rgba(33,30,24,.28), 0 2px 8px rgba(33,30,24,.08);
}

/* Runtime-swappable variables (Tweaks panel mutates these in M1). The display font here is
   overridden by --font-display from @theme by default; the M1 font Tweak rewrites --font-display. */
:root {
  --accent: #2E7D4F;
  --accent-bg: #E7F0E9;
  --accent-ink: #1E5D39;
  /* density (driven by [data-density] on <html>) */
  --row-py: 17px; --gutter: 34px; --card-pad: 20px;
}
[data-density="compact"] { --row-py: 11px; --gutter: 26px; --card-pad: 15px; }

@layer base {
  html { font-size: 14px; }
  body {
    font-family: var(--font-body);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }                                        /* bg-paper text-ink applied via className in layout.tsx */
  ::selection { background: var(--accent-bg); }
}
```

> Tailwind v4 `@theme` auto-generates utilities: `bg-paper`, `text-ink-2`, `border-rule`,
> `shadow-pop`, `font-display`, `font-mono`, etc. — these are how components style themselves.
> `--gutter`/density vars are consumed in M1's dense views; defined now so the system is complete.

### 4.2 Typography scale (prototype §2 — applied as utilities/arbitrary values where used)

| Role | Family | Notes |
|---|---|---|
| View title (`.vtitle`) | display | 34px / 600 / `tracking-[-.01em]` / `leading-none` |
| Brand logo | display | 23px / 600 / `tracking-[.05em]` |
| Nav item | body | 13.5px / 500 |
| Nav section label | mono | 9.5px / uppercase / `tracking-[.16em]` / ink-3 |
| Mono metadata/labels | mono | uppercase labels use `tracking-[.08em–.16em]` |

Base 14px; `text-wrap: pretty` on multi-line prose (used in M1 content, not the empty shell).

### 4.3 Fonts via `next/font/google`

In `app/layout.tsx`, load and expose as CSS variables on `<html>`:
- `Spectral` (weights 400,500,600,700) → `--font-spectral`
- `Hanken_Grotesk` (400,500,600,700) → `--font-hanken`
- `Geist_Mono` (400,500,600) → `--font-geist-mono`
- `Newsreader` + `Source_Serif_4` → `--font-newsreader`, `--font-source-serif` (loaded for M1's font
  Tweak; not applied to anything in M0a)

The five `font.variable` class names go on `<html className={...}>`; `@theme` binds `--font-display`
etc. to them. Default display font = Spectral.

---

## 5. App shell — `(app)/layout.tsx`

Reproduces `specula.css` `.app` / `.main` / `.view`:

- Root: `<div className="grid grid-cols-[236px_1fr] h-screen overflow-hidden">`.
- Left: `<Sidebar />` (§6).
- Right: `<main className="overflow-y-auto relative">` containing `{children}`. Each view supplies its
  own `.view`-equivalent wrapper via `<ViewShell>` (`max-w-[1180px] mx-auto px-[34px] pt-[30px]
  pb-16`). Main column owns the scroll; sidebar is fixed-width and does not scroll with it.
- Custom scrollbar styling (`.main::-webkit-scrollbar` → 10px, `rule-2` thumb) ported as a small CSS
  rule in `globals.css` (webkit-only; harmless elsewhere).

The `<main key={pathname}>` remount-to-replay-entrance trick from the prototype is **deferred to M1**
(no entrance animations in M0a); M0a's `<main>` has no `key`.

---

## 6. Sidebar — `components/sidebar.tsx` (client component)

Ports `app.jsx`'s `Sidebar` + `specula.css` `.side*`. Structure top→bottom:

1. **`.side`** container: `bg-panel border-r border-rule flex flex-col overflow-hidden`.
2. **Brand** (`.side-top`, `p-[22px_20px_16px] border-b border-rule`): `Specula` (display, 23px/600,
   `tracking-[.05em]`) + `role ledger` (mono, 10px, ink-2) on a baseline-aligned flex row.
3. **Sync row + Refresh (inert placeholders).** Render the exact markup/styling — the pulsing accent
   `.sync-dot` (the **one allowed** infinite animation, per §14), the mono "synced — · — new" line
   with em-dash placeholders (NO fabricated numbers — honors the derived-counts invariant), and the
   ink-filled Refresh button with the ↻ glyph. **The button is present but does nothing in M0a**
   (its real wiring to run status is M3); it is `disabled` with a `title="Available in a later
   milestone"` so it's honestly inert, not fake-functional.
4. **Nav** (`.nav`, `flex-1 overflow-y-auto p-[14px_12px]`), driven by `lib/nav.ts`:
   - Section labels (mono, 9.5px, uppercase, `tracking-[.16em]`, ink-3): **Pipeline**, **Intelligence**,
     **Configure**.
   - Items (Pipeline: Jobs, Approval queue, Companies · Intelligence: Insights · Configure: Search
     profiles, Targeting), each an active `<Link>` with icon + label.
   - **Active state** via `usePathname()`: the item whose `href` matches the current path gets `.on`
     styling (`bg-ink text-paper`); others `text-ink-2 hover:bg-panel-2 hover:text-ink`.
   - **Count badges:** the nav model supports an optional `count`/`alert` per item, rendered **only
     when present**. In M0a none is supplied → no badges. (M1/M2 supply derived counts; the
     warn-colored `alert` badge style for the Approval queue is implemented but unused until then.)
5. **Candidate card** (`.side-me`, `border-t border-rule p-3`): a `<Link href="/candidate">` styled
   `.me-card`, active when on `/candidate`. **Neutral placeholder** until auth/profile (M0b/M2): a
   generic avatar mark (e.g. `—` or a person glyph, NOT fabricated initials) + "Candidate" / "profile"
   labels. No real name is invented.

### Nav model (`lib/nav.ts`)

```ts
export type NavItem = { id: string; label: string; href: string; icon: IconName };
export type NavEntry = { section: string } | NavItem;

export const NAV: NavEntry[] = [
  { section: "Pipeline" },
  { id: "jobs",       label: "Jobs",           href: "/jobs",       icon: "jobs" },
  { id: "approvals",  label: "Approval queue",  href: "/approvals",  icon: "approvals" },
  { id: "companies",  label: "Companies",       href: "/companies",  icon: "companies" },
  { section: "Intelligence" },
  { id: "insights",   label: "Insights",        href: "/insights",   icon: "insights" },
  { section: "Configure" },
  { id: "profiles",   label: "Search profiles", href: "/profiles",   icon: "profiles" },
  { id: "targeting",  label: "Targeting",       href: "/targeting",  icon: "targeting" },
];
```

(The candidate card is rendered separately, not as a NAV entry, matching the prototype.)

### Icons (`components/icon.tsx`)

Port the prototype's inline-SVG `Icon` set (single `<path>` strings, `stroke:currentColor;
stroke-width:1.4; fill:none; round caps`, 16px viewBox). Keys needed in M0a: `jobs`, `approvals`,
`companies`, `insights`, `profiles`, `targeting` (+ `candidate` for the card). Copy the exact path
data from `prototype/specula/ui.jsx`.

---

## 7. Empty routed views

Seven `page.tsx` files, each a thin call to a shared `<ViewShell>` (`components/view-shell.tsx`) that
renders the `.vhead` chrome (serif `.vtitle` + `.vsub` explainer, bottom-ruled) plus a quiet empty
state. **`/` redirects to `/jobs`** (default screen) via `redirect("/jobs")` in `app/page.tsx`.

`ViewShell` props: `label` (→ `data-screen-label` on the root, per spec §12 "behavioral parity"),
`title`, `sub`. Each view root: `<section data-screen-label={label} className="...">`.

Titles/subs (concise; real explanatory copy is refined in M1 alongside content):

| Route | `data-screen-label` | Title | Sub (placeholder) |
|---|---|---|---|
| `/jobs` | `jobs` | Jobs | The scored, deduplicated pool of roles. Arrives in M1. |
| `/approvals` | `approvals` | Approval queue | Candidate companies awaiting your decision. Arrives in M1. |
| `/companies` | `companies` | Companies | Your registry of tracked companies. Arrives in M1. |
| `/insights` | `insights` | Insights | Personal market intelligence. Arrives in M1. |
| `/profiles` | `profiles` | Search profiles | Lenses over the shared pool. Arrives in M1. |
| `/targeting` | `targeting` | Targeting | What you want — roles, must-haves, values. Arrives in M1. |
| `/candidate` | `candidate` | Candidate | Who you are — the profile that drives scoring. Arrives in M1. |

The empty state below the header is a single muted line (mono, ink-3) — deliberately minimal; M1
replaces the body with real content.

---

## 8. Testing

**Playwright E2E** (`e2e/shell.spec.ts`) — set up Playwright in `apps/web` (config + `@playwright/test`
dev dep + a `test:e2e` script; the dev server is started by the Playwright webServer config). Cases:
1. Visiting `/` redirects to `/jobs`; the jobs view renders (its `data-screen-label="jobs"` present).
2. The sidebar renders the brand "Specula" and all six nav items (Jobs, Approval queue, Companies,
   Insights, Search profiles, Targeting) + the candidate card.
3. Clicking each of the six nav items navigates to its route and that view's `data-screen-label`
   appears; the candidate card navigates to `/candidate` (the seventh route).
4. The active nav item carries the `.on` styling for the current route (assert the active item's
   distinguishing class/state matches the path).
5. The page background computes to the paper token (`#FBFAF6`) — a cheap proof the token system is live.

**Component test** (Sidebar): renders all nav items from the model; given a pathname, exactly the
matching item is marked active; count badges are absent when no count is supplied (invariant guard).
*(Test runner: M0a introduces the web test runner the Phase-0 `justfile test` comment anticipated.
Use Playwright's component testing OR Vitest + Testing Library — the plan picks one; both satisfy
"renders nav, marks active, no fabricated badges".)*

**Gates unchanged from Phase 0:** `pnpm lint`, `pnpm typecheck`, `pnpm format:check`, `pnpm build`
all stay green; the new tests run via a `test:e2e` (and/or `test`) script and in CI.

---

## 9. Acceptance (M0a definition of done)

1. `pnpm dev` → the app shows the **editorial shell**: warm paper background, Spectral wordmark, the
   sidebar with grouped nav, on `/jobs` by default.
2. All seven routes are reachable from the sidebar; the active item is highlighted (ink fill) for the
   current route; main column scrolls, sidebar is fixed.
3. Fonts are live: Spectral (display), Hanken Grotesk (body), Geist Mono (mono) — verifiable in the
   wordmark, view titles, and mono labels.
4. **No fabricated data anywhere**: no hard-coded counts, no fake "synced 2d ago", no invented
   candidate name. Placeholders are visibly inert.
5. The Tweaks panel is **absent** (deferred), but the token system is tweak-ready (`:root` vars
   present; swapping `--accent` in devtools recolors accent usages).
6. `pnpm lint && pnpm typecheck && pnpm format:check && pnpm build` green; Playwright smoke + the
   Sidebar component test pass; CI green.
7. The create-next-app boilerplate (demo `page.tsx`, Geist tokens, `apps/web/README.md` cruft) is
   gone.

---

## 10. Open questions / notes for the plan

- **Web test runner choice** (Playwright CT vs Vitest+RTL for the component test) — the plan picks
  one and states why; either satisfies §8. (Playwright is already needed for E2E, so reusing it for
  the component test avoids a second runner — a reasonable default.)
- **`disabled` Refresh button styling** — keep the prototype's visual (ink fill) but at reduced
  affordance (cursor/opacity) so "inert" reads honestly. Minor; plan decides exact treatment.
- Everything else is specified above with exact values; no TBDs.
