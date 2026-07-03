# Specula M1d-1 — Tweaks panel (runtime theming): Design Spec

> **Status:** proposed design (written on best-judgment while awaiting review), ready for user review
> → then `writing-plans`.
> **Milestone:** M1d-1 — the first of two M1d sub-pieces (M1d = "Tweaks panel + visual-regression").
> M1d-1 = the runtime-theming Tweaks panel; **M1d-2 = pixel visual-regression** (built after, so it
> snapshots the tweaked states too). After M1d, **M1 is done**; M2 = real FastAPI + persistence.
> **Sources of truth:** prototype `app.jsx` (the `TWEAK_DEFAULTS` + the root-apply effect + the
> `<TweaksPanel>` usage), `tweaks-panel.jsx` (the control *shapes* only — NOT its design-tool
> host-protocol machinery), `views.css` (`[data-layout="cards"]`, `[data-density="compact"]`),
> production spec §10 (tweaks persist via API in M2), `CLAUDE.md`.
> **Conflict rule:** visuals → prototype wins; architecture/behavior → spec wins.

---

## 1. Goal & boundary

Add the **Tweaks panel** — the runtime personalization surface that switches the match-score style,
the Jobs layout, the display font, the accent color, and the spacing density, applying instantly and
persisting client-locally. This activates two things already built-but-dormant (the `MatchMeter`
figure/ring styles from M1a; the Newsreader/Source-Serif fonts M0a preloaded) and adds the cards
layout.

**In scope (M1d-1):**
1. **`TweaksProvider`** (client context) holding the 5 tweak values, backed by `localStorage`, applying
   the *global* tweaks (accent / font / density) to `<html>` via an effect; exposes `useTweaks()`.
2. **A FOUC-avoiding init script** (blocking, in the root `<head>`) that applies the persisted global
   tweaks before first paint — no theme flash.
3. **`TweaksPanel`** — a fixed glass panel (bottom-right) + a floating toggle button, with the 5
   controls; and a minimal set of `Tweak*` controls (segmented radio, select, color chips) rebuilt
   Tailwind-native (NOT the prototype's design-tool omelette scaffold).
4. **Wiring the 5 tweaks** to their consumers (details in §4).

**The 5 tweaks (defaults from `app.jsx` `TWEAK_DEFAULTS`):**

| Tweak | Options (default first) | Applies to |
|---|---|---|
| **mstyle** | `bars` · `figure` · `ring` | the `MatchMeter` `mstyle` prop (Jobs rows + drawer) |
| **layout** | `rows` · `cards` | the Jobs list (grid + card rows) |
| **font** | `Spectral` · `Newsreader` · `Source Serif 4` | `--font-display` (global) |
| **accent** | `#2E7D4F` · `#2D5BBF` · `#9A7A18` · `#7A4FB0` | `--accent` + derived (global) |
| **density** | `comfortable` · `compact` | `data-density` + Jobs compact extras |

**Out of scope (deferred, with owner):**
- **Pixel visual-regression** → **M1d-2** (its explicit deliverable; snapshots the tweaked states).
- **API-persisted per-user tweaks** → **M2** (spec §10). M1d-1 persists client-locally (localStorage)
  — the exact M2 shape (swap the storage backend, keep the provider API).
- **The design-tool host protocol** (`__activate_edit_mode` postMessage, on-disk EDITMODE rewriting)
  from `tweaks-panel.jsx` — that's Claude-Design infra, NOT the product. Not ported.
- **Draggable panel** — YAGNI; a fixed bottom-right panel + toggle is the product affordance.
- **A "replay intro" affordance** (spec §13.1) — nice-to-have; deferred (the intro's once-per-session
  reset is a `sessionStorage` clear, addable later).

**Invariants honored** (`CLAUDE.md`): tweaks are presentation-only — they never change data, counts,
scoring, or salary handling. No new infinite animation loops (the panel's controls use short
transitions only).

---

## 2. Architecture

- **`TweaksProvider`** (`"use client"`) wraps the `(app)` shell. State `{ mstyle, layout, density,
  accent, font }` initialized from `localStorage("specula_tweaks")` merged over the defaults (read in
  a mount effect to stay hydration-safe — SSR renders defaults, the effect reconciles). `setTweak(key,
  value)` updates state + writes localStorage. A second effect applies the **global** tweaks to
  `document.documentElement`:
  - `style.setProperty("--accent", accent)`,
    `--accent-bg = color-mix(in srgb, ${accent} 15%, var(--color-paper))`,
    `--accent-ink = color-mix(in srgb, ${accent} 70%, #000)`;
  - `--font-display = var(--font-${slug}), serif` where slug ∈ `spectral | newsreader | source-serif`
    (the next/font vars already on `<html>`);
  - `setAttribute("data-density", density === "compact" ? "compact" : "regular")`.
  `mstyle` + `layout` are NOT global CSS — they change component markup, so they're consumed via
  `useTweaks()` by `JobsView` (§4).
- **FOUC init script** — a blocking inline `<script dangerouslySetInnerHTML>` in the root
  `app/layout.tsx` `<head>` that reads `localStorage("specula_tweaks")` and applies the same
  accent/font/density properties to `documentElement` *before first paint* (the next-themes pattern).
  This eliminates the color/font/spacing flash. (mstyle/layout are React markup — a persisted non-
  default may show its default for one frame before the mount effect reconciles; acceptable, since the
  flash-prone surfaces — color/font/spacing — are handled by the script. A cookie-backed SSR read
  would remove even that one frame; deferred as an optional refinement.)
- **Consumer wiring:** only the Jobs feature needs component changes (mstyle + cards + compact-extras);
  accent/font/density-spacing are global vars/attrs already consumed by every view.

---

## 3. Files

```
apps/web/src/
  lib/tweaks.tsx                       # CREATE (client) — TweaksProvider, useTweaks, defaults, apply-effect
  lib/tweaks-init.ts                   # CREATE — the FOUC init-script source string (+ a pure applyTweaks helper)
  app/layout.tsx                       # MODIFY — inject the FOUC <script> in <head>
  app/(app)/layout.tsx                 # MODIFY — wrap children in <TweaksProvider>; render <TweaksPanel/>
  components/tweaks/tweaks-panel.tsx    # CREATE (client) — the glass panel + toggle button
  components/tweaks/tweak-controls.tsx  # CREATE (client) — Segmented, SelectControl, ColorChips
  components/jobs/jobs-view.tsx         # MODIFY — read useTweaks(); pass mstyle/card/compact
  components/jobs/job-row.tsx           # MODIFY — accept mstyle/card/compact; card variant + compact extras
  components/jobs/job-drawer.tsx        # MODIFY — accept mstyle prop → MatchMeter
  # tests: co-located *.test.tsx (Vitest) + e2e/authed/tweaks.spec.ts (Playwright)
```

`lib/tweaks-init.ts` isolates the pure `applyTweaks(root, tweaks)` logic so it's shared by BOTH the
provider effect AND the init script (DRY), and unit-testable.

---

## 4. Wiring the 5 tweaks

- **accent** — global. The provider effect (+ init script) sets `--accent` and the two `color-mix`
  derivatives. Every accent consumer (`--color-accent`/`--color-accent-bg`/`--color-accent-ink` via
  `@theme`, plus the M1c intro/etc.) updates live. The 4 options are curated color chips.
- **font** — global. Sets `--font-display` to the chosen next/font var (all 3 preloaded). Every
  `font-display` element (serif titles) reflows to the chosen face.
- **density** — global spacing via `data-density` (already: `[data-density="compact"]` overrides
  `--row-py`/`--gutter`/`--card-pad`, consumed by the row padding etc.). **Compact extras** (Jobs-
  local, from `views.css:57-58`): `JobsView` passes `compact` to `JobRow`, which hides the rationale
  `<p>` and shrinks the title (20px→18px) when compact.
- **mstyle** — `JobsView` reads `tweaks.mstyle` and passes it to `JobRow` (→ `MatchMeter mstyle=`) and
  to `JobDrawer` (→ its `MatchMeter`). The atom already renders `bars`/`figure`/`ring`; this activates
  figure/ring (built M1a, unused until now). `MatchMeter` stays a context-free atom (receives the prop).
- **layout (cards)** — `JobsView` reads `tweaks.layout`. In `cards`: the list container becomes a
  2-col grid (`grid-cols-2 gap-[14px]`), the column header is hidden, and `JobRow` renders a **card
  variant** (from `views.css:61-66`): a bordered rounded card (`border rule`, `rounded-[14px]`,
  `p-[18px]`, `bg-card`, `shadow-card`, single-column), no index, with the `MatchMeter` full-width
  below a dashed top rule. `JobRow` gets a `card` prop selecting row vs card classes. The FLIP (M1c)
  still measures positions in either layout (grid or list), so lens re-sort keeps working in cards.

---

## 5. The Tweaks panel (product build — NOT the omelette scaffold)

- **Toggle button:** a fixed circular button, bottom-right (`fixed bottom-4 right-4 z-50`), glass, with
  a sliders/tune glyph; toggles the panel. `aria-label="Tweaks"`, `aria-expanded`.
- **Panel:** a fixed glass card (`bottom-16 right-4`, `w-[280px]`, `bg-paper/85` + `backdrop-blur`,
  `border`, `rounded-[14px]`, `shadow-pop`), matching the prototype's frosted aesthetic. A header
  ("Tweaks" + close ✕) and a body with 3 sections:
  - **Signature** — Match score `<Segmented>` (bars/figure/ring), Job layout `<Segmented>` (rows/cards).
  - **Type & color** — Display font `<SelectControl>` (Spectral/Newsreader/Source Serif 4), Accent
    `<ColorChips>` (the 4 hexes).
  - **Density** — Spacing `<Segmented>` (comfortable/compact).
- **Controls** (`tweak-controls.tsx`, Tailwind-native, minimal): `Segmented` (a labeled segmented
  radio, `role="radiogroup"`, options ≤3), `SelectControl` (a labeled `<select>`), `ColorChips` (a
  `role="radiogroup"` of color swatches with a check on the active one). Each takes `value` + `onChange`.
- Each control calls `setTweak(key, value)` → instant apply + persist. Reduced-motion: the panel's
  open/close + the segmented thumb use short transitions gated by `motion-safe:` (no motion under
  reduced-motion).

---

## 6. Persistence (client-local — the M2 shape)

`localStorage("specula_tweaks")` holds the JSON `{ mstyle, layout, density, accent, font }`. Read
(merged over defaults) on mount + by the init script; written on every `setTweak`. Corrupt/absent →
defaults. **M2** replaces the storage backend with an authenticated `GET/PATCH /me/tweaks` (per-user),
keeping the `useTweaks()` API identical — no consumer changes.

---

## 7. Testing

- **Unit (Vitest):**
  - `applyTweaks(root, tweaks)` (from `tweaks-init.ts`) sets the right `--accent`/`--accent-bg`/
    `--accent-ink`/`--font-display`/`data-density` on a fake root (assert the exact `color-mix`
    strings + the font var per option).
  - `TweaksProvider`/`useTweaks`: defaults when localStorage empty; reads a persisted value; `setTweak`
    updates + writes localStorage.
  - `TweaksPanel`: renders the 5 controls; toggling a control fires `setTweak` with the right value;
    the toggle button opens/closes the panel.
  - `JobsView`: passes `tweaks.mstyle` to `MatchMeter`; in `layout==="cards"` renders the grid + card
    rows (assert the card class / no colhead); in `density==="compact"` the JobRow hides the rationale.
  - `JobRow` card variant + compact variant render without crashing (structure assertions).
- **Authed E2E (Playwright, `e2e/authed/tweaks.spec.ts`):** open the panel via the toggle; switch
  Job-layout to `cards` → the list gains the grid/card DOM; switch Accent → `--accent` on `<html>`
  changes; reload → the tweak persisted (localStorage).
- **Gates:** `just lint/typecheck/test` + `pnpm build` + `pre-commit` + the E2E suite green; CI green.
- Plus my own browser-verify (drive all 5 tweaks via `just dev-web-noauth`, screenshot each).

---

## 8. Acceptance (M1d-1 definition of done)

1. A Tweaks toggle button opens a fixed glass panel with the 5 controls; each applies instantly.
2. **mstyle** switches the match meters between bars/figure/ring (figure/ring now live in-app).
3. **layout** switches the Jobs list between rows and a 2-col card grid (card rows, no index/colhead,
   full-width meter); the FLIP still works in both.
4. **font** switches `--font-display` (Spectral/Newsreader/Source Serif 4) across the serif titles.
5. **accent** switches `--accent` + its color-mix derivatives across every accent surface.
6. **density** switches the spacing (comfortable/compact) + hides the Jobs rationale / shrinks the
   title in compact.
7. Tweaks persist across reload (localStorage); the FOUC init script prevents a color/font/spacing
   flash on load.
8. `just lint && just typecheck && just test` + `pnpm build` + `pre-commit run --all-files` + E2E
   green; CI green.

---

## 9. Open considerations for the plan
- **Reuse `applyTweaks` in both the provider effect and the init script** (DRY) — the init script
  serializes a call to it (or an inlined equivalent) as a string; the provider imports it.
- **`color-mix` support** is universal in current evergreen browsers/Next 16 targets; the accent-bg/ink
  derivations use it (matching the prototype's `app.jsx`). No fallback needed.
- **mstyle/layout one-frame flash** (localStorage post-hydration) is accepted; note the cookie-SSR
  option if zero-flash on those is later required.
- **The Jobs feature is the only component-level consumer** — keep accent/font/density global (root),
  and pass only mstyle/card/compact down from `JobsView`. Do NOT make `MatchMeter` read context.
- **The FLIP + card layout interaction:** the M1c FLIP measures `offsetTop/offsetLeft` — valid in both
  the list and the 2-col grid, so no FLIP change is needed; confirm the card rows keep `data-fid`.
- Everything else is specified; no TBDs.
