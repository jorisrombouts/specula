# M1d-1 — Tweaks panel (runtime theming) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the runtime Tweaks panel — switch match-score style, Jobs layout, display font, accent color, and density, applying instantly and persisting client-locally — activating the dormant `MatchMeter` figure/ring styles and the preloaded fonts, plus a cards layout.

**Architecture:** A `TweaksProvider` (client context, localStorage-backed) applies the *global* tweaks (accent/font/density) to `<html>`; a blocking FOUC init script applies them before first paint. The panel + controls are Tailwind-native (not the prototype's design-tool omelette). Only the Jobs feature needs component wiring (mstyle → `MatchMeter` prop; cards layout; compact extras); accent/font/density are global CSS vars/attrs already consumed everywhere.

**Tech Stack:** Next.js 16 (RSC + client islands), React 19 (context, `useEffect`), TypeScript strict, Tailwind v4 (+ `color-mix`), Vitest + @testing-library/react, Playwright.

## Global Constraints

- **The 5 tweaks + defaults** (from prototype `app.jsx` `TWEAK_DEFAULTS`): `mstyle` (bars·figure·ring, default bars) · `layout` (rows·cards, default rows) · `font` (Spectral·Newsreader·Source Serif 4, default Spectral) · `accent` (#2E7D4F·#2D5BBF·#9A7A18·#7A4FB0, default #2E7D4F) · `density` (comfortable·compact, default comfortable).
- **Global tweaks apply to `<html>`:** `--accent` = the hex; `--accent-bg` = `color-mix(in srgb, ${accent} 15%, var(--color-paper))`; `--accent-ink` = `color-mix(in srgb, ${accent} 70%, #000)`; `--font-display` = `var(--font-${slug}), serif` (slug: Spectral→spectral, Newsreader→newsreader, Source Serif 4→source-serif — the next/font vars already on `<html>`); `data-density` = `compact` or `regular`.
- **`applyTweaks` is the single source** of that mapping — shared by the provider AND the init script (via a serialized `INIT_SCRIPT` string mirroring it).
- **Persistence = `localStorage("specula_tweaks")`** (the M2 shape). No design-tool host protocol. No draggable panel.
- **FOUC init script** runs before first paint (blocking, in the root `<head>`) → no color/font/spacing flash. mstyle/layout may show their default for one frame (accepted).
- **mstyle stays a `MatchMeter` prop** — the atom does NOT read context; `JobsView` passes it. Tweaks never change data/counts/scoring.
- **Tailwind-native**, real theme tokens; no prototype CSS import. TypeScript strict, no `any`. Commands run from `apps/web`. Testing = Vitest units + authed Playwright E2E (`e2e/authed/tweaks.spec.ts`, via the :3001 bypass).
- **Sources of truth:** prototype `app.jsx` (tweak system) + `views.css` `[data-layout="cards"]`/`[data-density="compact"]`, spec `docs/superpowers/specs/2026-07-03-m1d-1-tweaks-panel-design.md`.

---

### Task 1: Tweaks core (`applyTweaks` + init script + `TweaksProvider`)

**Files:**
- Create: `apps/web/src/lib/tweaks-init.ts`, `apps/web/src/lib/tweaks.tsx`
- Test: `apps/web/src/lib/tweaks-init.test.ts`, `apps/web/src/lib/tweaks.test.tsx`

**Interfaces:**
- Produces:
  - `Tweaks` type + `TWEAK_DEFAULTS`, `ACCENT_OPTIONS`, `FONT_OPTIONS`, `STORAGE_KEY`.
  - `applyTweaks(root: HTMLElement, t: Pick<Tweaks,"accent"|"font"|"density">): void`
  - `INIT_SCRIPT: string` (the blocking FOUC script body).
  - `<TweaksProvider>` + `useTweaks(): { tweaks: Tweaks; setTweak: <K extends keyof Tweaks>(k: K, v: Tweaks[K]) => void }`

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/lib/tweaks-init.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { applyTweaks, INIT_SCRIPT, TWEAK_DEFAULTS, STORAGE_KEY } from "@/lib/tweaks-init";

describe("applyTweaks", () => {
  it("sets accent (+ color-mix derivatives), font var, and density attr", () => {
    const root = document.createElement("html");
    applyTweaks(root, { accent: "#2D5BBF", font: "Newsreader", density: "compact" });
    expect(root.style.getPropertyValue("--accent")).toBe("#2D5BBF");
    expect(root.style.getPropertyValue("--accent-bg")).toBe(
      "color-mix(in srgb, #2D5BBF 15%, var(--color-paper))",
    );
    expect(root.style.getPropertyValue("--accent-ink")).toBe(
      "color-mix(in srgb, #2D5BBF 70%, #000)",
    );
    expect(root.style.getPropertyValue("--font-display")).toBe("var(--font-newsreader), serif");
    expect(root.getAttribute("data-density")).toBe("compact");
  });

  it("maps 'Source Serif 4' → --font-source-serif and comfortable → regular", () => {
    const root = document.createElement("html");
    applyTweaks(root, { accent: "#2E7D4F", font: "Source Serif 4", density: "comfortable" });
    expect(root.style.getPropertyValue("--font-display")).toBe("var(--font-source-serif), serif");
    expect(root.getAttribute("data-density")).toBe("regular");
  });

  it("INIT_SCRIPT applies persisted tweaks to documentElement before paint", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...TWEAK_DEFAULTS, accent: "#7A4FB0", font: "Newsreader" }),
    );
    // eslint-disable-next-line no-eval
    eval(INIT_SCRIPT);
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe("#7A4FB0");
    expect(document.documentElement.style.getPropertyValue("--font-display")).toBe(
      "var(--font-newsreader), serif",
    );
    localStorage.clear();
    document.documentElement.removeAttribute("style");
  });
});
```

Create `apps/web/src/lib/tweaks.test.tsx`:

```tsx
import { describe, it, expect, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import { TweaksProvider, useTweaks } from "@/lib/tweaks";
import { STORAGE_KEY } from "@/lib/tweaks-init";

afterEach(cleanup);
beforeEach(() => localStorage.clear());

function Probe() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <div>
      <span data-testid="mstyle">{tweaks.mstyle}</span>
      <button onClick={() => setTweak("mstyle", "ring")}>ring</button>
    </div>
  );
}

describe("TweaksProvider", () => {
  it("defaults when localStorage is empty", () => {
    render(<TweaksProvider><Probe /></TweaksProvider>);
    expect(screen.getByTestId("mstyle")).toHaveTextContent("bars");
  });

  it("reads a persisted tweak on mount", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ mstyle: "figure" }));
    render(<TweaksProvider><Probe /></TweaksProvider>);
    // reconciled by the mount effect
    expect(await screen.findByText("figure")).toBeInTheDocument();
  });

  it("setTweak updates state and persists to localStorage", () => {
    render(<TweaksProvider><Probe /></TweaksProvider>);
    act(() => {
      fireEvent.click(screen.getByText("ring"));
    });
    expect(screen.getByTestId("mstyle")).toHaveTextContent("ring");
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).mstyle).toBe("ring");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `pnpm test src/lib/tweaks-init.test.ts src/lib/tweaks.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `tweaks-init.ts`**

Create `apps/web/src/lib/tweaks-init.ts`:

```ts
export type Mstyle = "bars" | "figure" | "ring";
export type Layout = "rows" | "cards";
export type Density = "comfortable" | "compact";
export interface Tweaks {
  mstyle: Mstyle;
  layout: Layout;
  density: Density;
  accent: string;
  font: string;
}

export const TWEAK_DEFAULTS: Tweaks = {
  mstyle: "bars",
  layout: "rows",
  density: "comfortable",
  accent: "#2E7D4F",
  font: "Spectral",
};

export const ACCENT_OPTIONS = ["#2E7D4F", "#2D5BBF", "#9A7A18", "#7A4FB0"];
export const FONT_OPTIONS = ["Spectral", "Newsreader", "Source Serif 4"];
export const STORAGE_KEY = "specula_tweaks";

const FONT_VARS: Record<string, string> = {
  Spectral: "--font-spectral",
  Newsreader: "--font-newsreader",
  "Source Serif 4": "--font-source-serif",
};

// The single source of the global-tweak → CSS mapping. Shared by the provider
// effect and (mirrored as a string) by INIT_SCRIPT.
export function applyTweaks(
  root: HTMLElement,
  t: Pick<Tweaks, "accent" | "font" | "density">,
): void {
  root.style.setProperty("--accent", t.accent);
  root.style.setProperty(
    "--accent-bg",
    `color-mix(in srgb, ${t.accent} 15%, var(--color-paper))`,
  );
  root.style.setProperty("--accent-ink", `color-mix(in srgb, ${t.accent} 70%, #000)`);
  const fontVar = FONT_VARS[t.font] ?? FONT_VARS.Spectral;
  root.style.setProperty("--font-display", `var(${fontVar}), serif`);
  root.setAttribute("data-density", t.density === "compact" ? "compact" : "regular");
}

// Blocking pre-paint script: reads localStorage and applies the same mapping so
// accent/font/density never flash. Mirrors applyTweaks (can't import pre-React).
export const INIT_SCRIPT = `(function(){try{
var t=JSON.parse(localStorage.getItem(${JSON.stringify(STORAGE_KEY)})||"{}");
var r=document.documentElement;
var a=t.accent||${JSON.stringify(TWEAK_DEFAULTS.accent)};
r.style.setProperty("--accent",a);
r.style.setProperty("--accent-bg","color-mix(in srgb, "+a+" 15%, var(--color-paper))");
r.style.setProperty("--accent-ink","color-mix(in srgb, "+a+" 70%, #000)");
var fv={"Spectral":"--font-spectral","Newsreader":"--font-newsreader","Source Serif 4":"--font-source-serif"}[t.font||"Spectral"]||"--font-spectral";
r.style.setProperty("--font-display","var("+fv+"), serif");
r.setAttribute("data-density",t.density==="compact"?"compact":"regular");
}catch(e){}})();`;
```

- [ ] **Step 4: Implement `tweaks.tsx`**

Create `apps/web/src/lib/tweaks.tsx`:

```tsx
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  type Tweaks,
  TWEAK_DEFAULTS,
  STORAGE_KEY,
  applyTweaks,
} from "@/lib/tweaks-init";

type Ctx = {
  tweaks: Tweaks;
  setTweak: <K extends keyof Tweaks>(key: K, value: Tweaks[K]) => void;
};
const TweaksContext = createContext<Ctx | null>(null);

export function TweaksProvider({ children }: { children: React.ReactNode }) {
  const [tweaks, setTweaks] = useState<Tweaks>(TWEAK_DEFAULTS);

  // Reconcile from localStorage after mount (SSR renders defaults; the init
  // script already applied the CSS vars pre-paint).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setTweaks((t) => ({ ...t, ...(JSON.parse(raw) as Partial<Tweaks>) }));
    } catch {
      /* ignore */
    }
  }, []);

  // Apply + persist on change. Skip the FIRST run: the init script already
  // applied the pre-paint values, so applying defaults here would clobber them.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    applyTweaks(document.documentElement, tweaks);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tweaks));
    } catch {
      /* ignore */
    }
  }, [tweaks]);

  const setTweak = useCallback(
    <K extends keyof Tweaks>(key: K, value: Tweaks[K]) => {
      setTweaks((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  return (
    <TweaksContext.Provider value={{ tweaks, setTweak }}>
      {children}
    </TweaksContext.Provider>
  );
}

export function useTweaks(): Ctx {
  const ctx = useContext(TweaksContext);
  if (!ctx) throw new Error("useTweaks must be used within a TweaksProvider");
  return ctx;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pnpm test src/lib/tweaks-init.test.ts src/lib/tweaks.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 6: Gates + commit**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check` → all green.
```bash
git add apps/web/src/lib/tweaks-init.ts apps/web/src/lib/tweaks.tsx apps/web/src/lib/tweaks-init.test.ts apps/web/src/lib/tweaks.test.tsx
git commit -m "feat(web): tweaks core — applyTweaks, FOUC init script, TweaksProvider (M1d-1)"
```

---

### Task 2: Tweak controls + panel

**Files:**
- Create: `apps/web/src/components/tweaks/tweak-controls.tsx`, `apps/web/src/components/tweaks/tweaks-panel.tsx`
- Test: `apps/web/src/components/tweaks/tweaks-panel.test.tsx`

**Interfaces:**
- Consumes: `useTweaks` (Task 1) + `ACCENT_OPTIONS`/`FONT_OPTIONS`.
- Produces:
  - `Segmented({ label, value, options, onChange })`, `SelectControl({ label, value, options, onChange })`, `ColorChips({ label, value, options, onChange })`.
  - `TweaksPanel()` — `"use client"`, the toggle button + panel; reads/writes `useTweaks`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/tweaks/tweaks-panel.test.tsx`:

```tsx
import { describe, it, expect, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { TweaksProvider } from "@/lib/tweaks";
import { TweaksPanel } from "@/components/tweaks/tweaks-panel";
import { STORAGE_KEY } from "@/lib/tweaks-init";

afterEach(cleanup);
beforeEach(() => localStorage.clear());

function mount() {
  return render(
    <TweaksProvider>
      <TweaksPanel />
    </TweaksProvider>,
  );
}

describe("TweaksPanel", () => {
  it("opens on the toggle button and shows the 5 controls", () => {
    mount();
    // panel hidden until toggled
    expect(screen.queryByText("Match score")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /tweaks/i }));
    for (const label of ["Match score", "Job layout", "Display font", "Accent", "Spacing"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("switching Job layout to cards persists layout=cards", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /tweaks/i }));
    // the Job-layout segmented control has a 'cards' option
    fireEvent.click(screen.getByRole("radio", { name: "cards" }));
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).layout).toBe("cards");
  });

  it("closes on the ✕", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /tweaks/i }));
    fireEvent.click(screen.getByLabelText("Close tweaks"));
    expect(screen.queryByText("Match score")).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm test src/components/tweaks/tweaks-panel.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the controls**

Create `apps/web/src/components/tweaks/tweak-controls.tsx`:

```tsx
export function Segmented({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <span className="text-[11px] font-medium text-ink-2">{label}</span>
      <div role="radiogroup" className="flex gap-[2px] rounded-[8px] bg-panel-2 p-[2px]">
        {options.map((o) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={o === value}
            aria-label={o}
            onClick={() => onChange(o)}
            className={`flex-1 rounded-[6px] px-[6px] py-[4px] text-[11.5px] font-medium capitalize transition-colors motion-safe:transition-colors ${
              o === value ? "bg-card text-ink shadow-card" : "text-ink-2 hover:text-ink"
            }`}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SelectControl({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <span className="text-[11px] font-medium text-ink-2">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-[28px] rounded-[7px] border border-rule-2 bg-card px-[8px] text-[12px] text-ink"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

export function ColorChips({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <span className="text-[11px] font-medium text-ink-2">{label}</span>
      <div role="radiogroup" className="flex gap-[6px]">
        {options.map((o) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={o === value}
            aria-label={o}
            onClick={() => onChange(o)}
            style={{ background: o }}
            className={`h-[26px] flex-1 rounded-[6px] ${
              o === value ? "ring-2 ring-ink ring-offset-1" : "ring-1 ring-black/10"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement the panel**

Create `apps/web/src/components/tweaks/tweaks-panel.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useTweaks } from "@/lib/tweaks";
import { ACCENT_OPTIONS, FONT_OPTIONS } from "@/lib/tweaks-init";
import { Segmented, SelectControl, ColorChips } from "@/components/tweaks/tweak-controls";

export function TweaksPanel() {
  const { tweaks, setTweak } = useTweaks();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        aria-label="Tweaks"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-4 right-4 z-50 flex h-[38px] w-[38px] items-center justify-center rounded-full border border-rule-2 bg-paper/85 text-[16px] text-ink shadow-pop backdrop-blur"
      >
        ⚙
      </button>

      {open && (
        <div className="fixed bottom-[60px] right-4 z-50 flex w-[280px] flex-col rounded-[14px] border border-rule-2 bg-paper/90 shadow-pop backdrop-blur">
          <div className="flex items-center justify-between border-b border-rule px-[14px] py-[10px]">
            <b className="text-[12px] font-semibold">Tweaks</b>
            <button
              type="button"
              aria-label="Close tweaks"
              onClick={() => setOpen(false)}
              className="flex h-[22px] w-[22px] items-center justify-center rounded-[6px] text-ink-2 hover:bg-black/[0.06] hover:text-ink"
            >
              ✕
            </button>
          </div>
          <div className="flex flex-col gap-[12px] px-[14px] py-[12px]">
            <div className="font-mono text-[10px] uppercase tracking-[0.06em] text-ink-3">
              Signature
            </div>
            <Segmented
              label="Match score"
              value={tweaks.mstyle}
              options={["bars", "figure", "ring"]}
              onChange={(v) => setTweak("mstyle", v as typeof tweaks.mstyle)}
            />
            <Segmented
              label="Job layout"
              value={tweaks.layout}
              options={["rows", "cards"]}
              onChange={(v) => setTweak("layout", v as typeof tweaks.layout)}
            />
            <div className="font-mono text-[10px] uppercase tracking-[0.06em] text-ink-3">
              Type &amp; color
            </div>
            <SelectControl
              label="Display font"
              value={tweaks.font}
              options={FONT_OPTIONS}
              onChange={(v) => setTweak("font", v)}
            />
            <ColorChips
              label="Accent"
              value={tweaks.accent}
              options={ACCENT_OPTIONS}
              onChange={(v) => setTweak("accent", v)}
            />
            <div className="font-mono text-[10px] uppercase tracking-[0.06em] text-ink-3">
              Density
            </div>
            <Segmented
              label="Spacing"
              value={tweaks.density}
              options={["comfortable", "compact"]}
              onChange={(v) => setTweak("density", v as typeof tweaks.density)}
            />
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/components/tweaks/tweaks-panel.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Gates + commit**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check` → green.
```bash
git add apps/web/src/components/tweaks
git commit -m "feat(web): Tweaks panel + controls (segmented / select / color chips) (M1d-1)"
```

---

### Task 3: Mount the provider + FOUC init; wire the global tweaks live

**Files:**
- Modify: `apps/web/src/app/layout.tsx` (inject `INIT_SCRIPT`), `apps/web/src/app/(app)/layout.tsx` (wrap in `<TweaksProvider>` + render `<TweaksPanel/>`)
- Test: `apps/web/e2e/authed/tweaks.spec.ts`

**Interfaces:**
- Consumes: `INIT_SCRIPT` (Task 1), `TweaksProvider` (Task 1), `TweaksPanel` (Task 2).

- [ ] **Step 1: Write the failing E2E**

Create `apps/web/e2e/authed/tweaks.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("the tweaks panel opens, applies an accent, and persists across reload", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1"); // skip intro
    } catch {}
  });
  await page.goto("/jobs");
  await page.getByRole("button", { name: /tweaks/i }).click();
  // pick the blue accent (#2D5BBF)
  await page.getByRole("radio", { name: "#2D5BBF" }).click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--accent").trim(),
      ),
    )
    .toBe("#2D5BBF");
  // persisted → survives reload
  await page.reload();
  await expect
    .poll(() =>
      page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--accent").trim(),
      ),
    )
    .toBe("#2D5BBF");
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm exec playwright test --project=authed e2e/authed/tweaks.spec.ts`
Expected: FAIL — no tweaks button yet (panel not mounted).

- [ ] **Step 3: Inject the FOUC init script in the root layout**

In `apps/web/src/app/layout.tsx`, import `INIT_SCRIPT` and add a `<head>` with the blocking script (add `import { INIT_SCRIPT } from "@/lib/tweaks-init";` at the top, and put the `<head>` inside `<html>` before `<body>`):

```tsx
  return (
    <html
      lang="en"
      className={`${spectral.variable} ${hanken.variable} ${geistMono.variable} ${newsreader.variable} ${sourceSerif.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: INIT_SCRIPT }} />
      </head>
      <body className="bg-paper text-ink">{children}</body>
    </html>
  );
```

- [ ] **Step 4: Mount the provider + panel in the (app) layout**

In `apps/web/src/app/(app)/layout.tsx`, add the imports and wrap the returned tree:

```tsx
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { Sidebar } from "@/components/sidebar";
import { IntroGate } from "@/components/intro/intro-gate";
import { getJobsPool } from "@/lib/api/jobs";
import { TweaksProvider } from "@/lib/tweaks";
import { TweaksPanel } from "@/components/tweaks/tweaks-panel";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  const bypass =
    process.env.NODE_ENV !== "production" &&
    process.env.DEV_AUTH_BYPASS === "1";
  const user =
    session?.user ??
    (bypass ? { name: "Dev (bypass)", email: "dev@local" } : null);
  if (!user) redirect("/signin");
  const pool = getJobsPool();
  const roles = pool.length;
  const isNew = pool.filter((j) => j.isNew).length;
  return (
    <TweaksProvider>
      <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
        <IntroGate roles={roles} isNew={isNew} />
        <Sidebar user={user} />
        <main className="main-scroll relative overflow-y-auto">{children}</main>
      </div>
      <TweaksPanel />
    </TweaksProvider>
  );
}
```

- [ ] **Step 5: Run the E2E to verify it passes**

Run: `pnpm exec playwright test --project=authed e2e/authed/tweaks.spec.ts`
Expected: PASS — the panel opens, `--accent` becomes `#2D5BBF`, and it survives reload.

- [ ] **Step 6: Gates + commit**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check` → green (the full unit suite still passes; the layout changes are wiring).
```bash
git add "apps/web/src/app/layout.tsx" "apps/web/src/app/(app)/layout.tsx" apps/web/e2e/authed/tweaks.spec.ts
git commit -m "feat(web): mount TweaksProvider + panel + FOUC init (accent/font/density live) (M1d-1)"
```

---

### Task 4: Wire mstyle + density-compact into the Jobs feature

**Files:**
- Modify: `apps/web/src/components/jobs/jobs-view.tsx`, `apps/web/src/components/jobs/job-row.tsx`, `apps/web/src/components/jobs/job-drawer.tsx`
- Test: `apps/web/src/components/jobs/jobs-view.test.tsx` (extend)

**Interfaces:**
- Consumes: `useTweaks` (Task 1).
- Produces: `JobRow` gains `mstyle: Mstyle` + `compact: boolean` props (kept alongside `sig`/`exit`/`style` from M1c); `JobDrawer` gains `mstyle: Mstyle`.

- [ ] **Step 1: Write the failing test**

Extend `apps/web/src/components/jobs/jobs-view.test.tsx` — wrap the render in `TweaksProvider` and add tests. Add these imports at the top if missing: `import { TweaksProvider } from "@/lib/tweaks";` and `import { STORAGE_KEY } from "@/lib/tweaks-init";`. Since `JobsView` now calls `useTweaks()`, **every existing `render(<JobsView .../>)` in this file must be wrapped** — add a helper and use it:

```tsx
function renderView(tweaks?: Record<string, unknown>) {
  if (tweaks) localStorage.setItem(STORAGE_KEY, JSON.stringify(tweaks));
  return render(
    <TweaksProvider>
      <JobsView {...props} />
    </TweaksProvider>,
  );
}
```

Replace the existing `render(<JobsView {...props} />)` calls with `renderView()`, add a `beforeEach(() => localStorage.clear())`, and add:

```tsx
  it("passes the mstyle tweak to the row meters (figure style)", () => {
    const { container } = renderView({ mstyle: "figure" });
    // figure style renders the 54px number with data-style="figure"
    expect(container.querySelector('[data-style="figure"]')).not.toBeNull();
  });

  it("hides the row rationale under compact density", async () => {
    const { container } = renderView({ density: "compact" });
    // rationale paragraph carries data-jrat; hidden when compact
    await Promise.resolve();
    expect(container.querySelector("[data-jrat]")).toBeNull();
  });
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm test src/components/jobs/jobs-view.test.tsx`
Expected: FAIL — `useTweaks` throws (no provider) until JobsView reads it, and the mstyle/compact wiring isn't there.

- [ ] **Step 3: Wire JobsView**

In `apps/web/src/components/jobs/jobs-view.tsx`: add `import { useTweaks } from "@/lib/tweaks";`, read the tweaks, and pass `mstyle`/`compact` to `JobRow` and `mstyle` to `JobDrawer`. Add near the other hooks: `const { tweaks } = useTweaks();` then `const compact = tweaks.density === "compact";`. Update the row render and the drawer:

```tsx
        {list.map((j, i) => (
          <JobRow
            key={j.id}
            job={j}
            i={i}
            onOpen={openJob}
            sig={sig}
            mstyle={tweaks.mstyle}
            compact={compact}
          />
        ))}
```
and (in the exit-rows map) add `mstyle={tweaks.mstyle} compact={compact}` to that `<JobRow>` too; and the drawer:
```tsx
      {selected && (
        <JobDrawer
          job={selected}
          candidate={candidate}
          morphFrom={morphFrom}
          mstyle={tweaks.mstyle}
          onClose={() => {
            setSelected(null);
            setMorphFrom(null);
          }}
        />
      )}
```

- [ ] **Step 4: Wire JobRow (mstyle + compact extras)**

In `apps/web/src/components/jobs/job-row.tsx`: add `mstyle` + `compact` to the props type, pass `mstyle` to `<MatchMeter>`, tag the rationale with `data-jrat` + hide it when compact, and shrink the title when compact. Change the props destructure/type to include `mstyle` (type `import type { Job } from "@specula/shared-types"` already there; add `import type { Mstyle } from "@/lib/tweaks-init";`) and `compact`:

```tsx
  mstyle,
  compact = false,
  ...
  mstyle: Mstyle;
  compact?: boolean;
```
- the `<h3>` className adds a compact size: change its class to include `${compact ? "text-[18px]" : "text-[20px]"}` (replace the static `text-[20px]`);
- the rationale `<p>`: add `data-jrat` and hide when compact — wrap it: `{!compact && (<p data-jrat className="...">{job.rationale}</p>)}`;
- the meter: `<MatchMeter job={job} mstyle={mstyle} replay={sig} countUp={!exit} />` (replace the hard-coded `mstyle="bars"`).

- [ ] **Step 5: Wire JobDrawer**

In `apps/web/src/components/jobs/job-drawer.tsx`: add `mstyle: Mstyle` to the props (import the type), and pass it to the drawer's `<MatchMeter>` (replace `mstyle="bars"` with `mstyle={mstyle}`). Keep `reveal={!morphFrom} replay={job.id}`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm test src/components/jobs/jobs-view.test.tsx src/components/jobs/job-row.test.tsx src/components/jobs/job-drawer.test.tsx`
Expected: PASS. (The job-row/job-drawer tests from M1c must also render fine — they call `<JobRow .../>`/`<JobDrawer .../>` directly; add `mstyle="bars"` to those existing test render calls since it's now required. The drawer test may already pass `bars`; if `mstyle` is required, update those call sites.)

- [ ] **Step 7: Gates + commit**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check` → green.
```bash
git add apps/web/src/components/jobs
git commit -m "feat(web): wire mstyle + compact tweaks into Jobs (meters + rationale/title) (M1d-1)"
```

---

### Task 5: Cards layout + build gate

**Files:**
- Modify: `apps/web/src/components/jobs/jobs-view.tsx`, `apps/web/src/components/jobs/job-row.tsx`
- Test: `apps/web/src/components/jobs/jobs-view.test.tsx` (extend), `apps/web/e2e/authed/tweaks.spec.ts` (extend)

**Interfaces:**
- Consumes: `useTweaks` (Task 1). `JobRow` gains `card: boolean`.

- [ ] **Step 1: Write the failing tests**

Extend `apps/web/src/components/jobs/jobs-view.test.tsx`:

```tsx
  it("renders the Jobs list as a 2-col card grid under layout=cards (no colhead)", () => {
    const { container } = renderView({ layout: "cards" });
    // the list container becomes a grid; the column header is hidden
    expect(container.querySelector("[data-jlist][data-cards]")).not.toBeNull();
    expect(container.querySelector("[data-colhead]")).toBeNull();
    // rows carry the card marker
    expect(container.querySelector("article[data-fid][data-card]")).not.toBeNull();
  });
```

Extend `apps/web/e2e/authed/tweaks.spec.ts`:

```ts
test("switching Job layout to cards restyles the list as a card grid", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1");
    } catch {}
  });
  await page.goto("/jobs");
  await page.getByRole("button", { name: /tweaks/i }).click();
  await page.getByRole("radio", { name: "cards" }).click();
  await expect(page.locator("[data-jlist][data-cards]")).toBeVisible();
  await expect(page.locator("article[data-fid][data-card]").first()).toBeVisible();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `pnpm test src/components/jobs/jobs-view.test.tsx`
Expected: FAIL — no `data-cards`/`data-card`/`data-colhead` markers yet.

- [ ] **Step 3: JobsView — card grid + markers**

In `apps/web/src/components/jobs/jobs-view.tsx`: derive `const cards = tweaks.layout === "cards";`. Tag the column-header div with `data-colhead` and hide it when cards; tag the list container with `data-jlist` (+ `data-cards` when cards) and switch its class to a 2-col grid when cards; pass `card={cards}` to each `JobRow`.
- Column header: add `data-colhead` and `${cards ? "hidden" : ""}` to its className.
- List container: change `<div className="relative" ref={listRef}>` to:
```tsx
      <div
        ref={listRef}
        data-jlist
        data-cards={cards ? "" : undefined}
        className={cards ? "relative grid grid-cols-2 gap-[14px] pt-[14px]" : "relative"}
      >
```
- Pass `card={cards}` on both the live-rows `<JobRow>` and the exit-rows `<JobRow>`.

- [ ] **Step 4: JobRow — card variant**

In `apps/web/src/components/jobs/job-row.tsx`: add `card = false` to props (`card?: boolean`). When `card`, the `<article>` uses the card classes (bordered rounded card, single column, no hover panel), the index `<div>` is hidden, and the meter sits full-width under a dashed top rule. Add `data-card={card ? "" : undefined}` to the `<article>`. Replace the `<article>` className with a card-aware version:

```tsx
      className={
        card
          ? "relative isolate flex cursor-pointer flex-col gap-[10px] rounded-[14px] border border-rule bg-card p-[18px] shadow-card"
          : "relative isolate grid cursor-pointer grid-cols-[30px_1fr_248px] items-start gap-[18px] border-b border-rule py-[var(--row-py)] " +
            "opacity-0 motion-safe:[animation:rowIn_0.5s_cubic-bezier(0.2,0.7,0.2,1)_forwards] motion-reduce:opacity-100 before:absolute before:inset-y-0 before:-inset-x-[14px] before:-z-10 before:rounded-[8px] before:bg-panel before:opacity-0 before:transition-opacity hover:before:opacity-100"
      }
```
(keep the `exit` branch handling as in M1c — apply the exit classes when `exit`, else the card/row classes; structure the className so `exit` still wins as before). Hide the index in card mode: wrap the `.jidx` div in `{!card && (<div ...>{String(i+1)...}</div>)}`. Put the meter full-width with a dashed top in card mode: wrap `<MatchMeter>` so in card mode it's preceded by a `border-t border-dashed border-rule pt-[14px] mt-[14px] w-full` wrapper.

> Keep the M1c animation/exit logic intact — the card branch is an alternate presentation of the same row; `data-fid` stays on the `<article>` so the FLIP still measures it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pnpm test src/components/jobs/jobs-view.test.tsx`
Expected: PASS.

- [ ] **Step 6: Full gates + BUILD + E2E**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check && pnpm build` — all green (`pnpm build` is a required gate; if a TLS `SELF_SIGNED_CERT_IN_CHAIN` error, re-run as `NODE_EXTRA_CA_CERTS="$HOME/.corp-ca.pem" pnpm build`).
Then the full E2E: `pnpm test:e2e` (public + authed, incl. the tweaks specs).
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/jobs "apps/web/e2e/authed/tweaks.spec.ts"
git commit -m "feat(web): Jobs cards layout tweak (2-col grid, card rows) (M1d-1)"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** Task 1 → §2 provider + §6 persistence + the FOUC script. Task 2 → §5 panel + controls. Task 3 → §2 mount + FOUC live (accent/font/density global). Task 4 → §4 mstyle + density-compact. Task 5 → §4 cards layout + §8 build. Deferred (visual-regression → M1d-2, API persistence → M2) honored.
- **Type consistency:** `Tweaks`/`applyTweaks`/`useTweaks`/`INIT_SCRIPT` (Task 1) are consumed by Tasks 2–5. `Mstyle` flows into `JobRow`/`JobDrawer` props (Task 4). `MatchMeter` `mstyle` prop is the M1a atom's (bars/figure/ring).
- **The clobber-avoidance is deliberate:** the provider's apply-effect skips its first run (the init script already applied pre-paint); only user changes + the localStorage reconcile re-apply. Verified against a flash.
- **Existing M1c tests must be updated** for the new required `mstyle` prop on `JobRow`/`JobDrawer` and the `TweaksProvider` wrapper on `JobsView` — Tasks 4/5 call this out.
- **FLIP unaffected:** the card rows keep `data-fid`; `offsetTop/offsetLeft` measure in the grid too.
- **No new E2E flakiness:** the tweaks E2E asserts `--accent`/DOM end-states via `expect.poll`, skips the intro, runs on the :3001 bypass server.
