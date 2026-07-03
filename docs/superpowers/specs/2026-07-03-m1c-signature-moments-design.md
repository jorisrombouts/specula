# Specula M1c — The four signature moments (motion) : Design Spec

> **Status:** proposed design (written on best-judgment while awaiting review), ready for user review
> → then `writing-plans`.
> **Milestone:** M1c — the motion layer over the static M1b views. Brings the four signature moments
> to life + entrances + reduced-motion. Sequence: M1b ✅ (8 static views) → **M1c (motion)** → M1d
> (Tweaks panel + pixel visual-regression) → then M1 done, M2 = real FastAPI + persistence.
> **Sources of truth:** prototype `intro.jsx` (assembling intro), `jobs.jsx` (FLIP + morph + reveal
> wiring), `app.jsx` (intro mount + `main key={view}` per-view entrance), `specula.css`/`views.css`
> (the exact keyframes/durations/easings), the M1a `MatchMeter` atom (already has `reveal`/`replay`/
> `countUp`), design spec §13 (four moments) + §14 (motion & a11y), `CLAUDE.md`.
> **Conflict rule:** visuals → prototype wins; architecture/behavior → spec wins.

---

## 1. Goal & boundary

Add the motion layer to the static M1b views: the **four signature moments** (assembling intro,
FLIP lens re-sort, scoring reveal, row→drawer morph) plus **entrances** and a **`prefers-reduced-motion`
gate** across all of it. This is the craft layer — the spec calls these "the four signature
interactions [that] carry the craft" (§0) and mandates all four survive to production (§13).

**In scope (M1c):**
1. **Motion foundation** — a shared `usePrefersReducedMotion()` hook; the entrance `@keyframes`
   (`rowIn`, `viewIn`, `introMark`/`introRule`/`introLine`/`introFade`/`introLeave`) + their reduced-
   motion `@media` override in `globals.css`; and the **M1b-1 carry-forward**: extract a single
   `scoredList(pool, lens, sort): Job[]` used by BOTH `getJobs` (lib/api) and `JobsView` — so the FLIP
   and the HTTP contract can't drift.
2. **Playwright E2E harness (authed, dev-mode + bypass)** — configure Playwright's `webServer` to run
   the dev server with `DEV_AUTH_BYPASS=1` so the auth-gated views are reachable in E2E; a smoke spec
   that an authed view loads. This finally enables spec §12's "E2E for the four signature moments."
   The bypass stays **production-disabled** (it's gated on `NODE_ENV !== "production"`), so E2E runs
   against `next dev`, never a prod build.
3. **Assembling intro** (§13 9.1) — `IntroOverlay` + an `IntroGate` client wrapper: once-per-session
   via `sessionStorage("specula_intro")`, skippable (click / any keydown), ~2s, reduced-motion-aware,
   mounted in the auth-gated `(app)` layout. Counts up to the **derived** pool (13 roles / 7 new).
4. **FLIP lens re-sort** (§13 9.2) — in `JobsView`, a `useLayoutEffect` keyed on `lens|sort` flips
   surviving rows old→new position, animates leaving rows out, and re-sweeps each `MatchMeter` via the
   `replay` key. Reduced-motion short-circuits to an instant re-order.
5. **Scoring reveal** (§13 9.3) — the `MatchMeter` `reveal` mode (bars sweep + number counts up +
   "scoring…" label) when a drawer opens **not** from a row (no captured rects). Atom already supports
   it — this is wiring.
6. **Row → drawer morph** (§13 9.4) — `JobRow` captures its `.jtitle` + `.meter` rects on click and
   passes them to `JobDrawer`, which morphs the drawer's title (font-ratio scale) + meter (width-ratio
   scale, clamp `[0.3, 1.4]`) from those rects, with supporting content rising in and a `setTimeout`
   fallback on close. Reduced-motion → plain fade/slide (no morph).
7. **Entrances** (§14) — `rowIn` stagger on job rows (45ms × index), `viewIn` on each view section
   (replays on route change — Next remounts the page, mirroring the prototype's `main key={view}`),
   Insights bar-grow (CSS keyframe) + a `<CountUp>` client island for the "analysed" total. No infinite
   loops except the existing sidebar sync-dot.

**Out of scope (deferred, with owner):**
- **Pixel visual-regression** (snapshot the final frames) → **M1d** (its explicit deliverable). M1c's
  E2E asserts *behavior* (the moment happens, stable end-state); M1d's snapshots assert *pixels*.
- **Keyboard operability** (Tab/arrow nav in the Jobs list, roving focus, full focus states) →
  a **dedicated a11y pass** (tracked, not dropped — it joins the accumulated a11y items: lens
  `aria-current`, heading-outline, filter `aria-label`). Esc-closes-drawer is already done (M1b-1). A
  thorough single a11y pass is more production-grade than bolting keyboard nav onto the motion work.
- **The Tweaks panel** (runtime mstyle/layout/density/accent/font) → **M1d**. M1c hard-codes the
  defaults the atoms already use (`mstyle="bars"`, comfortable density).
- Real data/persistence → M2. (The FLIP works on the client-derived list; §13 9.2's "while the new
  list resolves" is an M2 async concern — in M1c the list resolves synchronously.)

**Invariants honored** (`CLAUDE.md`): the intro counts up to the **derived** pool (13/7), not the
prototype's cosmetic 47/11. No new decorative infinite loops. Salary/counts unaffected. Motion never
changes data — it only animates the already-correct render.

---

## 2. Architecture

- **Animated surfaces are client components** (spec §10): `JobsView`, `JobRow`, `JobDrawer`,
  `MatchMeter` (all already `"use client"` from M1a/M1b) + the new `IntroOverlay`/`IntroGate` +
  `<CountUp>`. The Insights bar-grow is **CSS-only** (works in the server component); only its
  count-up number is a small client island.
- **Two motion techniques, matching the prototype:**
  - **CSS `@keyframes`** for one-shot entrances (rowIn/viewIn/intro/bar-grow). Declarative, cheap,
    reduced-motion via a single `@media (prefers-reduced-motion: reduce)` block.
  - **WAAPI (`element.animate(...)`)** in `useLayoutEffect` for the FLIP + morph + drawer close —
    imperative, needs measured rects. Reduced-motion via the `usePrefersReducedMotion()` hook (skip
    the `.animate()` call).
- **`usePrefersReducedMotion()`** — a `useSyncExternalStore` hook over
  `matchMedia("(prefers-reduced-motion: reduce)")`, SSR-safe (returns `false` on the server, updates
  on mount + on change). One source of truth for all JS-driven motion.
- **Hydration safety:** entrances are CSS (run after paint, no hydration mismatch). The intro renders
  only after mount (an effect flips a `mounted` flag) so the server never emits it → no flash, no
  mismatch. FLIP/morph run in `useLayoutEffect` (client-only). No animation state is server-rendered.

---

## 3. Files

```
apps/web/src/
  lib/use-prefers-reduced-motion.ts     # CREATE — the shared hook
  lib/jobs-scoring.ts                    # CREATE — scoredList(pool, lens, sort): Job[] (M1b-1 dedup)
  lib/api/jobs.ts                        # MODIFY — getJobs() calls scoredList()
  app/globals.css                        # MODIFY — entrance/intro keyframes + reduced-motion @media
  components/intro/intro-overlay.tsx     # CREATE (client) — the assembling intro
  components/intro/intro-gate.tsx        # CREATE (client) — sessionStorage once-per-session mount
  app/(app)/layout.tsx                   # MODIFY — mount <IntroGate/> (still behind the auth guard)
  components/jobs/jobs-view.tsx          # MODIFY — client-side list via scoredList + FLIP + exit + viewIn
  components/jobs/job-row.tsx            # MODIFY — rect capture on click + rowIn stagger; replay meter
  components/jobs/job-drawer.tsx         # MODIFY — morph (from rects) + reveal (no rects) + close fallback
  lib/flip.ts                            # CREATE — pure FLIP/morph math (position diff, scale clamp)
  components/insights/count-up.tsx       # CREATE (client) — <CountUp value> island for "analysed"
  components/insights/insights-view.tsx  # MODIFY — CSS bar-grow classes + <CountUp> for the total
  # tests: co-located *.test.ts(x) (Vitest) + e2e/*.spec.ts (Playwright)
  e2e/                                   # signature-moment E2E specs (authed via bypass)
playwright.config.ts                     # MODIFY — webServer runs dev + DEV_AUTH_BYPASS=1
.github/workflows/ci.yml                 # MODIFY — the e2e job runs the authed signature-moment specs
```

`lib/flip.ts` isolates the only genuinely unit-testable animation logic (rect→transform math + the
`[0.3,1.4]` scale clamp) from the DOM-imperative wiring — so the math is TDD'd and the wiring is
E2E-verified.

---

## 4. The four moments (exact port)

### 4.1 Assembling intro (`intro.jsx` + `specula.css:134–153`)
- `IntroOverlay`: fixed `paper` overlay (`z-200`), centered — serif mark "Specula" (`introMark`:
  blur+letter-spacing settle), a rule that draws to 316px (`introRule`), the mono tag, 5 thin lines
  scaling in staggered (`introLine`, delays `0.62 + i*0.1`s), a stat line `synced · {N} roles tracked
  · {M} new this week` where **N/M are derived (13/7)** and N counts up (`useCountUp`), and the
  "click anywhere to enter" skip hint. Dismiss on click or any keydown → `introLeave` (slide up
  101%, 640ms) → `onDone`.
- **Reduced-motion:** the `@media` block flattens all intro keyframes to ~0s; the auto-dismiss timer
  is 250ms (vs 2000ms) and the leave is instant; the count-up is off.
- **`IntroGate`** (client): on mount, reads `sessionStorage("specula_intro")`; if unset, renders
  `<IntroOverlay onDone={() => sessionStorage.setItem("specula_intro","1")}/>` then unmounts it. Only
  renders after mount (so SSR emits nothing). Mounted in `(app)/layout.tsx` — i.e. **only after auth**.

### 4.2 FLIP lens re-sort (`jobs.jsx:307–337`)
- `JobsView` computes the displayed list via `scoredList(pool, lens, sort)` (client-side, already the
  case) and keeps a `useRef` of each row's last `{top,left,width}` keyed by `data-fid`.
- A `useLayoutEffect` keyed on `sig = lens + "|" + sort`: measure new positions; for each surviving
  row whose position changed, `el.animate([{transform: translate(oldΔ)}, {transform: none}], {560ms,
  cubic-bezier(.3,.9,.3,1)})`; for rows that left the set, render a transient absolutely-positioned
  copy that plays `rowExit` then clears (`setExiting`). Skip entirely when reduced-motion.
- Each `MatchMeter` gets `replay={sig}` so it re-sweeps its bars/number on every re-sort.

### 4.3 Scoring reveal (`MatchMeter` atom, already built)
- The drawer's `MatchMeter` uses `reveal={!morphFrom}`: when the drawer opens **not** from a row
  (no captured rects — e.g. a future command-palette/deep-link open), the meter plays its reveal
  (delayed bar sweep + count-up + "scoring…"→"match index" label). When opened from a row, the morph
  carries the meter instead (no reveal). Atom already implements both via `reveal`/`replay`/`countUp`.

### 4.4 Row → drawer morph (`jobs.jsx:14–25` capture + `129–172` morph)
- `JobRow.onClick` measures its `.jtitle` + `.meter` `getBoundingClientRect()` (+ the title's computed
  font-size) and calls `onOpen(job, { title: rect, meter: rect })`. `JobsView` holds `morphFrom`.
- `JobDrawer` (when `morphFrom` present), in `useLayoutEffect`: fade the scrim in; morph the drawer
  `.dr-title` from the row title (translate Δ + `scale = clamp(srcFont/destFont, 0.3, 1.4)`, 540ms
  cubic-bezier(.4,0,.12,1), `fill:backwards`), morph the meter from the row meter (width-ratio scale,
  40ms delay); the remaining header/sections rise in staggered (120 + n*38ms). Close: scrim fades,
  panel slides `translateX(46px)` + fades (300ms) with a `setTimeout(360)` fallback firing `onClose`.
- **Reduced-motion:** skip the morph — plain slide-in (the current M1b behavior) + instant close.
- The pure rect→transform math (Δx/Δy, the font/width ratios, the `[0.3,1.4]` clamp) lives in
  `lib/flip.ts` and is unit-tested; the `.animate()` wiring is E2E-verified.

---

## 5. Entrances (§14)
- **Rows:** `JobRow` gets `animation: rowIn .5s ... forwards` with `animationDelay: i*45ms`
  (staggered). Reduced-motion `@media` flattens it (opacity 1, no transform).
- **Views:** each view's root `<section>` gets a `viewIn` class (`opacity 0→1, translateY 8px→0`,
  0.4s). Because Next remounts the page component on route change, this replays per navigation (the
  prototype's `main key={view}` behavior — free here).
- **Insights:** the demand/seniority/mode/salary/active bars grow from 0 via a CSS `@keyframes`
  (width/flex 0→final) — CSS-only, works in the server component, reduced-motion via `@media`. The
  "analysed" number uses a `<CountUp value={insights.totalAnalysed}>` client island (the rest of the
  panel stays server-rendered).

---

## 6. Testing (production-grade: deterministic units + authed E2E)

Two complementary layers (pixel visual-regression is M1d):

- **Vitest unit/wiring tests (deterministic):**
  - `usePrefersReducedMotion` — returns false on server/no-match, true when the query matches, updates
    on change.
  - `lib/flip.ts` — the position-diff + `scale = clamp(ratio, 0.3, 1.4)` math (exact numbers).
  - `scoredList` — parity with `getJobs`' orchestration (same filter→score→sort result); a regression
    guard that the two paths agree.
  - `IntroGate` — renders the overlay when `sessionStorage` is unset, and NOT when set (once-per-
    session); dismiss calls `onDone` + sets the key.
  - `MatchMeter` reveal — the `reveal`/label-state behavior (already partly covered; assert
    "scoring…"→"match index").
  - `<CountUp>` — renders the final value; reduced-motion shows it immediately.
- **Playwright E2E (authed, dev-mode + `DEV_AUTH_BYPASS=1`) — the four moments' behavior:**
  - **Intro:** first load shows the overlay; click dismisses it; a second navigation in the same
    session does NOT re-show it.
  - **FLIP:** on `/jobs`, switching a lens re-orders the row set (the first row's `data-fid` changes)
    and the meters are present post-sort.
  - **Morph:** clicking a job row opens the drawer with the same title + a `MatchMeter`; Esc closes it.
  - **Reveal:** (kept minimal — asserted at the unit level since there's no non-row open path in M1c).
  - Assertions target **stable end-states** (post-animation), not mid-frames, to avoid timing
    flakiness; where needed, `prefers-reduced-motion` is emulated to make the end-state immediate.
- **Gates:** `just lint/typecheck/test` + `pnpm build` + the Playwright e2e job + `pre-commit` green;
  CI green. Plus my own real-browser drive (via `just dev-web-noauth`) to eyeball the actual motion.

---

## 7. Acceptance (M1c definition of done)
1. First app load of a session shows the assembling intro (after auth); it's skippable and doesn't
   re-show that session; reduced-motion collapses it; its counts are derived (13/7).
2. Switching a lens/sort on `/jobs` FLIPs the surviving rows to their new ranked positions, exits the
   leavers, and re-sweeps the meters; reduced-motion re-orders instantly.
3. Clicking a job row morphs its title + meter into the drawer header; closing animates out (with the
   fallback); reduced-motion falls back to the plain slide-in.
4. The `MatchMeter` reveal mode is wired for non-row drawer opens; entrances (rowIn stagger, viewIn,
   Insights bar-grow + analysed count-up) play; all honor reduced-motion; no new infinite loops.
5. `scoredList` single-sources the Jobs orchestration (getJobs + JobsView agree); the Playwright E2E
   harness runs the authed signature-moment specs via the bypass (dev-mode; prod build unaffected).
6. `just lint && just typecheck && just test` + `pnpm build` + e2e + `pre-commit run --all-files`
   green; CI (api + web incl. e2e) green.

---

## 8. Open considerations for the plan
- **`usePrefersReducedMotion` must be SSR-safe** (`useSyncExternalStore` with a server snapshot of
  `false`); do not read `matchMedia` during render.
- **Intro flash:** `IntroGate` renders nothing until a mount effect runs — so SSR/first paint never
  shows the overlay, avoiding a flash-then-hide on returning sessions.
- **FLIP + morph share the `data-fid`/rect plumbing** already present on `JobRow` (M1b-1 kept
  `data-fid`); the morph capture reuses the row's DOM refs.
- **E2E stability:** run against `next dev` with the bypass; assert end-states; emulate reduced-motion
  for deterministic timing where a moment's end-state is otherwise animation-gated. Keep the specs
  few and behavioral — pixel diffing is M1d.
- **Reduced-motion is one gate, two implementations:** the `@media` block (CSS entrances/intro/bars)
  and the `usePrefersReducedMotion()` hook (WAAPI FLIP/morph). Both must be present.
- Everything else is specified; no TBDs.
