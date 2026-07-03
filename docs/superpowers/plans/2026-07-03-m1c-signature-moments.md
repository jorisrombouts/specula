# M1c — The four signature moments (motion) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the motion layer to the static M1b views — the four signature moments (assembling intro, FLIP lens re-sort, scoring reveal, row→drawer morph) + entrances + a `prefers-reduced-motion` gate — ported faithfully from the prototype's WAAPI/keyframe techniques.

**Architecture:** CSS `@keyframes` (+ Tailwind `motion-safe:` variants) for one-shot entrances/intro; WAAPI `element.animate()` in `useLayoutEffect` for the FLIP/morph/close; a shared SSR-safe `usePrefersReducedMotion()` hook gates the JS-driven motion. Pure animation math lives in `lib/flip.ts` (unit-tested); the DOM-imperative wiring is verified by authed Playwright E2E (via the dev-only auth bypass, on a second dev server so the existing unauth-redirect specs still pass).

**Tech Stack:** Next.js 16 (client components), React 19 (`useLayoutEffect`/`useSyncExternalStore`), Web Animations API, TypeScript strict, Tailwind v4, Vitest + @testing-library/react, Playwright.

## Global Constraints

- **Faithful port.** The moments port from `prototype/specula/intro.jsx`, `jobs.jsx` (FLIP `:307–337`, morph `:129–186`, JobRow `:14–56`), and `specula.css` keyframes (`:134–153` intro, `:80` viewIn, rowIn/rowExit in `views.css:26–54`). Durations/easings verbatim. Do NOT import prototype CSS — translate to `globals.css` keyframes / Tailwind arbitrary animations.
- **Reduced-motion is mandatory** on intro / FLIP / morph / entrances. Two implementations: the `usePrefersReducedMotion()` hook (JS/WAAPI paths) and Tailwind `motion-safe:`/`motion-reduce:` variants + a `@media (prefers-reduced-motion: reduce)` block for the intro keyframes.
- **No new infinite loops** — only the existing sidebar sync-dot pulse may loop.
- **Counts DERIVED** — the intro counts up to the real pool (13 roles / 7 new), never the prototype's cosmetic 47/11.
- **SSR-safe.** `usePrefersReducedMotion` uses `useSyncExternalStore` (server snapshot `false`). `IntroGate` renders nothing until a mount effect runs (no SSR flash, no hydration mismatch). FLIP/morph run only in `useLayoutEffect`.
- **The auth bypass stays production-disabled** (gated on `NODE_ENV !== "production"` in `(app)/layout.tsx`). Authed E2E runs against `next dev` (dev mode), never a prod build. Do NOT weaken the gate.
- **TypeScript strict, no `any`.** Commands run from `apps/web` unless noted. Testing = Vitest units (`import { describe, it, expect, afterEach } from "vitest"`; RTL) + Playwright E2E (`e2e/authed/*.spec.ts`).
- **Sources of truth:** the prototype files above, spec `docs/superpowers/specs/2026-07-03-m1c-signature-moments-design.md`.

---

### Task 1: Motion foundation (hook + `scoredList` dedup + `flip.ts` math + entrance keyframes)

**Files:**
- Create: `apps/web/src/lib/use-prefers-reduced-motion.ts`, `apps/web/src/lib/jobs-scoring.ts`, `apps/web/src/lib/flip.ts`
- Test: `apps/web/src/lib/use-prefers-reduced-motion.test.tsx`, `apps/web/src/lib/jobs-scoring.test.ts`, `apps/web/src/lib/flip.test.ts`
- Modify: `apps/web/src/lib/api/jobs.ts` (getJobs → `scoredList`), `apps/web/src/components/jobs/jobs-view.tsx` (list → `scoredList`), `apps/web/src/app/globals.css` (entrance/intro keyframes)

**Interfaces:**
- Produces:
  - `usePrefersReducedMotion(): boolean` — SSR-safe (`false` on server).
  - `scoredList(pool: Job[], lens: string, sort: JobSort): Job[]` — the filter→score→sort orchestration.
  - `flipDelta(prev: {top:number;left:number}, next: {top:number;left:number}): {dx:number;dy:number} | null`
  - `morphScale(src: number, dest: number): number` — `clamp(src/dest, 0.3, 1.4)`.
  - CSS: `@keyframes rowIn/rowExit/viewIn/introMark/introRule/introLine/introFade/introLeave/barGrow` + a `@media (prefers-reduced-motion: reduce)` block.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/lib/flip.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { flipDelta, morphScale } from "@/lib/flip";

describe("flip math", () => {
  it("flipDelta returns null when unmoved, delta when moved", () => {
    expect(flipDelta({ top: 10, left: 5 }, { top: 10, left: 5 })).toBeNull();
    expect(flipDelta({ top: 40, left: 5 }, { top: 10, left: 5 })).toEqual({ dx: 0, dy: 30 });
  });
  it("morphScale is src/dest clamped to [0.3, 1.4]", () => {
    expect(morphScale(20, 25)).toBeCloseTo(0.8);
    expect(morphScale(200, 10)).toBe(1.4); // clamp high
    expect(morphScale(1, 10)).toBe(0.3); // clamp low
  });
});
```

Create `apps/web/src/lib/jobs-scoring.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { scoredList } from "@/lib/jobs-scoring";
import { getJobsPool, getJobs } from "@/lib/api/jobs";

describe("scoredList", () => {
  it("matches getJobs' orchestration (single source of truth)", () => {
    const pool = getJobsPool();
    for (const lens of ["all", "remote", "foreign"] as const) {
      const direct = scoredList(pool, lens, "match").map((j) => [j.id, j.match]);
      const viaRoute = getJobs(lens, "match").jobs.map((j) => [j.id, j.match]);
      expect(direct).toEqual(viaRoute);
    }
  });
  it("re-scores per lens (foreign changes loc/match vs all)", () => {
    const pool = getJobsPool();
    const all = scoredList(pool, "all", "match");
    const foreign = scoredList(pool, "foreign", "match");
    expect(foreign.length).toBeLessThan(all.length);
  });
});
```

Create `apps/web/src/lib/use-prefers-reduced-motion.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

afterEach(cleanup);

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

describe("usePrefersReducedMotion", () => {
  it("returns false when the query does not match", () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);
  });
  it("returns true when the query matches", () => {
    mockMatchMedia(true);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm test src/lib/flip.test.ts src/lib/jobs-scoring.test.ts src/lib/use-prefers-reduced-motion.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the three lib modules**

Create `apps/web/src/lib/flip.ts`:

```ts
export function flipDelta(
  prev: { top: number; left: number },
  next: { top: number; left: number },
): { dx: number; dy: number } | null {
  const dx = prev.left - next.left;
  const dy = prev.top - next.top;
  if (dx === 0 && dy === 0) return null;
  return { dx, dy };
}

// Shared-element morph scale: source size over destination size, clamped so a
// wildly different pair never produces an absurd transform (prototype §9).
export function morphScale(src: number, dest: number): number {
  return Math.max(0.3, Math.min(src / dest, 1.4));
}
```

Create `apps/web/src/lib/jobs-scoring.ts`:

```ts
import type { Job, JobSort } from "@specula/shared-types";
import { filterByLens, scoreForLens, sortJobs } from "@/lib/seed/logic";

// Single source of the Jobs filter→score→sort orchestration. Used by both the
// /api/jobs route (getJobs) and the client JobsView, so the HTTP contract and
// the FLIP-animated client list can never drift. M2: the pool comes from the API.
export function scoredList(pool: Job[], lens: string, sort: JobSort): Job[] {
  const scored = filterByLens(pool, lens).map((job) => ({
    ...job,
    ...scoreForLens(job, lens),
  }));
  return sortJobs(scored, sort);
}
```

Create `apps/web/src/lib/use-prefers-reduced-motion.ts`:

```ts
"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(cb: () => void): () => void {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false, // server snapshot
  );
}
```

- [ ] **Step 4: Wire `scoredList` into both callers (the M1b-1 dedup)**

In `apps/web/src/lib/api/jobs.ts`, replace the body of `getJobs` to use `scoredList` (drop the now-unused `filterByLens`/`scoreForLens`/`sortJobs` imports, keep `deriveLensSummaries`):

```ts
import type { JobSort, JobsResponse, Job } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";
import { scoredList } from "@/lib/jobs-scoring";

export function getJobsPool(): Job[] {
  return jobs.slice();
}

export function getJob(id: string): Job | null {
  return jobs.find((j) => j.id === id) ?? null;
}

export function getJobs(lens: string, sort: JobSort): JobsResponse {
  return {
    jobs: scoredList(jobs, lens, sort),
    lenses: deriveLensSummaries(lenses, jobs),
    sort,
  };
}
```

In `apps/web/src/components/jobs/jobs-view.tsx`, replace the inline list computation + its imports. Change the imports line `import { filterByLens, scoreForLens, sortJobs } from "@/lib/seed/logic";` to `import { scoredList } from "@/lib/jobs-scoring";`, and replace:

```tsx
  const list = sortJobs(
    filterByLens(pool, lens).map((j) => ({ ...j, ...scoreForLens(j, lens) })),
    sort,
  );
```

with:

```tsx
  const list = scoredList(pool, lens, sort);
```

- [ ] **Step 5: Add the entrance + intro keyframes to `globals.css`**

Append to `apps/web/src/app/globals.css` (after the existing `drawerIn` keyframe):

```css
/* ---- M1c entrances (one-shot; gated via Tailwind motion-safe: at call sites) ---- */
@keyframes rowIn {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes rowExit {
  from {
    opacity: 1;
    transform: none;
  }
  to {
    opacity: 0;
    transform: translateX(30px);
  }
}
@keyframes viewIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes barGrow {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

/* ---- M1c assembling intro (specula.css:134-153) ---- */
@keyframes introMark {
  from {
    opacity: 0;
    transform: translateY(16px);
    letter-spacing: 0.22em;
    filter: blur(6px);
  }
  to {
    opacity: 1;
    transform: none;
    letter-spacing: 0.02em;
    filter: none;
  }
}
@keyframes introRule {
  to {
    width: 316px;
  }
}
@keyframes introLine {
  to {
    transform: scaleX(1);
  }
}
@keyframes introFade {
  to {
    opacity: 1;
  }
}
@keyframes introLeave {
  to {
    transform: translateY(-101%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .intro-anim {
    animation-duration: 0.01s !important;
    animation-delay: 0s !important;
  }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm test src/lib/flip.test.ts src/lib/jobs-scoring.test.ts src/lib/use-prefers-reduced-motion.test.tsx`
Expected: PASS (7 tests).

- [ ] **Step 7: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green (the full suite still passes — `getJobs`/`JobsView` behavior is unchanged, just single-sourced).

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/lib/use-prefers-reduced-motion.ts apps/web/src/lib/jobs-scoring.ts apps/web/src/lib/flip.ts apps/web/src/lib/*.test.ts* apps/web/src/lib/api/jobs.ts apps/web/src/components/jobs/jobs-view.tsx apps/web/src/app/globals.css
git commit -m "feat(web): motion foundation — reduced-motion hook, scoredList dedup, flip math, entrance keyframes (M1c)"
```

---

### Task 2: Playwright authed E2E harness (two servers: public + bypass)

**Files:**
- Modify: `apps/web/playwright.config.ts`
- Create: `apps/web/e2e/authed/smoke.spec.ts`

**Interfaces:**
- Produces: a `authed` Playwright project (baseURL `http://localhost:3001`, matching `e2e/authed/*.spec.ts`) served by a second `next dev` with `DEV_AUTH_BYPASS=1`; the existing `public` tests stay on `:3000` (no bypass).

> **Why two servers:** the existing `e2e/shell.spec.ts` asserts unauthenticated `/jobs` → `/signin`. Enabling the bypass on that server would break it. So the plain `:3000` server keeps the unauth-redirect coverage, and a separate bypass `:3001` server serves the authed signature-moment specs. The bypass is dev-only (prod build can't activate it).

- [ ] **Step 1: Write the failing authed smoke spec**

Create `apps/web/e2e/authed/smoke.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1) — so the
// auth guard is bypassed and the app views render without a Google login.
test("an authed visit to /jobs renders the Jobs view (no redirect)", async ({
  page,
}) => {
  // skip the once-per-session intro so it never covers the view (only the
  // intro spec tests the intro itself)
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1");
    } catch {}
  });
  await page.goto("/jobs");
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.getByRole("heading", { name: "Jobs", level: 1 })).toBeVisible();
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm exec playwright test --project=authed`
Expected: FAIL — no `authed` project / no `:3001` server configured yet (config error or connection refused).

- [ ] **Step 3: Configure the two-server, two-project harness**

Replace `apps/web/playwright.config.ts` with:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: { trace: "on-first-retry" },
  projects: [
    {
      name: "public",
      testIgnore: /authed\//,
      use: { ...devices["Desktop Chrome"], baseURL: "http://localhost:3000" },
    },
    {
      name: "authed",
      testMatch: /authed\//,
      use: { ...devices["Desktop Chrome"], baseURL: "http://localhost:3001" },
    },
  ],
  webServer: [
    {
      command: "pnpm dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "pnpm dev --port 3001",
      url: "http://localhost:3001",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { DEV_AUTH_BYPASS: "1" },
    },
  ],
});
```

- [ ] **Step 4: Run both projects to verify green**

Run: `pnpm test:e2e`
Expected: PASS — the `public` project's `shell.spec.ts` (unauth redirects, still on :3000) AND the `authed` project's `smoke.spec.ts` (/jobs renders on :3001) all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/playwright.config.ts apps/web/e2e/authed/smoke.spec.ts
git commit -m "test(web): authed Playwright harness (bypass on :3001) + public unauth server on :3000 (M1c)"
```

---

### Task 3: Assembling intro (IntroOverlay + IntroGate + mount)

**Files:**
- Create: `apps/web/src/components/intro/intro-overlay.tsx`, `apps/web/src/components/intro/intro-gate.tsx`
- Test: `apps/web/src/components/intro/intro-gate.test.tsx`, `apps/web/e2e/authed/intro.spec.ts`
- Modify: `apps/web/src/app/(app)/layout.tsx` (mount `<IntroGate/>`)

**Interfaces:**
- Consumes: `usePrefersReducedMotion` (Task 1); `useCountUp` from `@/lib/use-count-up`; `getJobsPool` from `@/lib/api/jobs` (for the derived count, read in the RSC layout and passed as props).
- Produces:
  - `IntroOverlay({ roles: number, isNew: number, onDone: () => void })` — `"use client"`.
  - `IntroGate({ roles: number, isNew: number })` — `"use client"`, once-per-session via `sessionStorage`.

> **Derived counts:** the RSC `layout.tsx` computes `roles = getJobsPool().length` (13) and `isNew = getJobsPool().filter(j => j.isNew).length` (7) and passes them in — honoring the derived-counts invariant (not the prototype's 47/11).

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/components/intro/intro-gate.test.tsx`:

```tsx
import { describe, it, expect, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { IntroGate } from "@/components/intro/intro-gate";

afterEach(cleanup);
beforeEach(() => sessionStorage.clear());

describe("IntroGate", () => {
  it("renders the intro once per session (absent when the flag is set)", () => {
    const { rerender } = render(<IntroGate roles={13} isNew={7} />);
    // first mount, flag unset → overlay shows
    expect(screen.getByText("Specula")).toBeInTheDocument();
    // simulate a later mount in the same session with the flag set
    sessionStorage.setItem("specula_intro", "1");
    cleanup();
    rerender(<IntroGate roles={13} isNew={7} />);
    expect(screen.queryByText("Specula")).toBeNull();
  });

  it("shows the DERIVED counts (13 roles / 7 new)", () => {
    render(<IntroGate roles={13} isNew={7} />);
    expect(screen.getByText(/roles tracked/)).toHaveTextContent("13");
    expect(screen.getByText(/roles tracked/)).toHaveTextContent("7");
  });
});
```

Create `apps/web/e2e/authed/intro.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("the assembling intro shows on first load, dismisses on click, and does not recur", async ({
  page,
}) => {
  await page.goto("/jobs");
  const mark = page.getByText("Specula", { exact: true });
  await expect(mark).toBeVisible();
  await page.mouse.click(400, 400); // "click anywhere to enter"
  await expect(mark).toBeHidden();
  // a second navigation in the same session does NOT re-show it
  await page.goto("/companies");
  await expect(page.getByText("Specula", { exact: true })).toBeHidden();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `pnpm test src/components/intro/intro-gate.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement IntroOverlay (from `intro.jsx` + `specula.css:134-153`)**

Create `apps/web/src/components/intro/intro-overlay.tsx`. The `.intro-anim` class ties each animated element to the reduced-motion `@media` block (Task 1); the count-up is disabled under reduced-motion.

```tsx
"use client";

import { useEffect, useState } from "react";
import { useCountUp } from "@/lib/use-count-up";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

export function IntroOverlay({
  roles,
  isNew,
  onDone,
}: {
  roles: number;
  isNew: number;
  onDone: () => void;
}) {
  const reduce = usePrefersReducedMotion();
  const [leaving, setLeaving] = useState(false);
  const rolesShown = useCountUp(roles, !reduce, 1500);

  useEffect(() => {
    const finish = () => {
      setLeaving((was) => {
        if (!was) setTimeout(onDone, reduce ? 0 : 640);
        return true;
      });
    };
    const t = setTimeout(finish, reduce ? 250 : 2000);
    const onKey = () => finish();
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dismiss = () =>
    setLeaving((was) => {
      if (!was) setTimeout(onDone, reduce ? 0 : 640);
      return true;
    });

  return (
    <div
      onClick={dismiss}
      className={`fixed inset-0 z-[200] flex cursor-pointer flex-col items-center justify-center overflow-hidden bg-paper ${leaving ? "[animation:introLeave_0.64s_cubic-bezier(0.6,0,0.25,1)_forwards]" : ""}`}
    >
      <div className="relative text-center">
        <div className="intro-anim font-display text-[86px] font-semibold leading-[0.9] tracking-[0.02em] text-ink opacity-0 [animation:introMark_1s_cubic-bezier(0.2,0.7,0.2,1)_0.15s_forwards]">
          Specula
        </div>
        <div className="intro-anim mx-auto mt-[24px] h-[2px] w-0 bg-ink [animation:introRule_0.85s_cubic-bezier(0.6,0,0.15,1)_0.6s_forwards]" />
        <div className="intro-anim mt-[18px] font-mono text-[13px] uppercase tracking-[0.26em] text-ink-2 opacity-0 [animation:introFade_0.7s_ease_0.95s_forwards]">
          personal role ledger
        </div>
        <div className="mx-auto mt-[34px] flex w-[316px] flex-col gap-[10px]">
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className="intro-anim h-px origin-left scale-x-0 bg-rule-2 [animation:introLine_0.55s_cubic-bezier(0.4,0,0.2,1)_forwards]"
              style={{ animationDelay: `${0.62 + i * 0.1}s` }}
            />
          ))}
        </div>
        <div className="intro-anim mt-[28px] font-mono text-[12px] text-ink-2 opacity-0 [animation:introFade_0.7s_ease_1.2s_forwards]">
          synced · <b className="font-semibold text-ink">{rolesShown}</b> roles
          tracked · <b className="font-semibold text-ink">{isNew}</b> new this
          week
        </div>
      </div>
      <div className="intro-anim absolute bottom-[40px] left-0 right-0 text-center font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3 opacity-0 [animation:introFade_0.7s_ease_1.6s_forwards]">
        click anywhere to enter
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement IntroGate**

Create `apps/web/src/components/intro/intro-gate.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { IntroOverlay } from "@/components/intro/intro-overlay";

const KEY = "specula_intro";

export function IntroGate({ roles, isNew }: { roles: number; isNew: number }) {
  // Only decide after mount so SSR/first paint never emit the overlay (no flash
  // for returning sessions, no hydration mismatch).
  const [show, setShow] = useState(false);
  useEffect(() => {
    try {
      if (!sessionStorage.getItem(KEY)) setShow(true);
    } catch {
      /* sessionStorage unavailable → skip the intro */
    }
  }, []);

  if (!show) return null;
  return (
    <IntroOverlay
      roles={roles}
      isNew={isNew}
      onDone={() => {
        try {
          sessionStorage.setItem(KEY, "1");
        } catch {
          /* ignore */
        }
        setShow(false);
      }}
    />
  );
}
```

> **Test note:** the unit test's first assertion relies on `sessionStorage` being empty (the `beforeEach` clears it) — the overlay appears after the mount effect runs, which RTL flushes synchronously. If the first `getByText` flakes on effect timing, wrap the render in `act(() => {})` from `@testing-library/react`.

- [ ] **Step 5: Mount IntroGate in the auth-gated layout**

In `apps/web/src/app/(app)/layout.tsx`, add the import and the derived counts, and render `<IntroGate/>` inside the returned tree (it renders as a client island above the shell). Add near the top: `import { IntroGate } from "@/components/intro/intro-gate";` and `import { getJobsPool } from "@/lib/api/jobs";`. Then compute the counts before the return and add the element:

```tsx
  if (!user) redirect("/signin");
  const pool = getJobsPool();
  const roles = pool.length;
  const isNew = pool.filter((j) => j.isNew).length;
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <IntroGate roles={roles} isNew={isNew} />
      <Sidebar user={user} />
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm test src/components/intro/intro-gate.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 7: Run gates + the intro E2E**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Then: `pnpm exec playwright test --project=authed e2e/authed/intro.spec.ts`
Expected: all green — the intro shows, dismisses on click, and doesn't recur.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/intro apps/web/src/components/intro/intro-gate.test.tsx apps/web/e2e/authed/intro.spec.ts "apps/web/src/app/(app)/layout.tsx"
git commit -m "feat(web): assembling intro (IntroOverlay + once-per-session gate, derived counts) (M1c)"
```

---

### Task 4: FLIP lens re-sort (JobsView FLIP + JobRow entrance/exit + meter replay)

**Files:**
- Modify: `apps/web/src/components/jobs/jobs-view.tsx`, `apps/web/src/components/jobs/job-row.tsx`
- Test: `apps/web/src/components/jobs/job-row.test.tsx` (extend), `apps/web/e2e/authed/flip.spec.ts`

**Interfaces:**
- Consumes: `flipDelta` + `usePrefersReducedMotion` (Task 1); the row's `data-fid`.
- Produces: `JobRow({ job, i, onOpen, sig, exit?, style? })` — `onOpen: (job: Job, rects?: MorphRects) => void` (rects added in Task 5; here `onOpen(job)` still works); `sig: string` drives the `MatchMeter` `replay`; `exit` renders the transient leaving copy.

> This task establishes the `sig` prop + `exit` mode + row entrance on `JobRow`; Task 5 adds the rect capture to the same `onClick`.

- [ ] **Step 1: Write the failing FLIP E2E**

Create `apps/web/e2e/authed/flip.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("switching a lens re-sorts the job rows (FLIP) and keeps meters", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1"); // skip intro
    } catch {}
  });
  await page.goto("/jobs");
  const rows = page.locator("article[data-fid]:not([data-exit])");
  await expect(rows.first()).toBeVisible();
  const firstBefore = await rows.first().getAttribute("data-fid");
  // switch to a lens that re-scopes/re-scores the pool
  await page.getByRole("button", { name: /Foreign HQ/ }).click();
  await expect(rows.first()).toBeVisible();
  // the set changed (fewer rows or a new leader) — assert row count differs from all-lens 13
  await expect(rows).not.toHaveCount(13);
  // meters still render (a match number is visible in the first row)
  await expect(rows.first().locator("text=/\\d+/").first()).toBeVisible();
  const firstAfter = await rows.first().getAttribute("data-fid");
  expect(firstAfter).not.toBe(null);
  void firstBefore;
});
```

- [ ] **Step 2: Run it to verify it fails (or is unstable) pre-implementation**

Run: `pnpm exec playwright test --project=authed e2e/authed/flip.spec.ts`
Expected: the lens switch works (M1b already re-sorts), but there's no FLIP animation yet. This E2E asserts the end-state (set changed + meters present), so it may already pass structurally — run it after Step 4 to confirm it stays green with the animation added. (If it passes now, that's fine — it's the regression guard for the animated version.)

- [ ] **Step 3: Extend JobRow — `sig` prop, meter `replay`, entrance, exit mode, `data-exit`**

Replace `apps/web/src/components/jobs/job-row.tsx` with (adds `sig`/`exit`/`style`, the `rowIn` entrance via `motion-safe:`, and `data-exit` for the FLIP query; keeps the M1b structure):

```tsx
import type { Job } from "@specula/shared-types";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Tag } from "@/components/atoms/tag";

export function JobRow({
  job,
  i,
  onOpen,
  sig,
  exit = false,
  style,
}: {
  job: Job;
  i: number;
  onOpen: (job: Job) => void;
  sig: string;
  exit?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <article
      data-fid={job.id}
      data-exit={exit ? "" : undefined}
      onClick={() => !exit && onOpen(job)}
      style={exit ? style : { animationDelay: `${i * 45}ms` }}
      className={
        "relative isolate grid grid-cols-[30px_1fr_248px] items-start gap-[18px] border-b border-rule py-[var(--row-py)] " +
        (exit
          ? "pointer-events-none z-0 [animation:rowExit_0.46s_cubic-bezier(0.4,0,0.6,1)_forwards]"
          : "cursor-pointer opacity-0 motion-safe:[animation:rowIn_0.5s_cubic-bezier(0.2,0.7,0.2,1)_forwards] motion-reduce:opacity-100 before:absolute before:inset-y-0 before:-inset-x-[14px] before:-z-10 before:rounded-[8px] before:bg-panel before:opacity-0 before:transition-opacity hover:before:opacity-100")
      }
    >
      <div className="pt-[4px] font-mono text-[13px] text-ink-3">
        {String(i + 1).padStart(2, "0")}
      </div>
      <div>
        <div className="flex flex-wrap items-center gap-[10px]">
          <h3 className="m-0 font-display text-[20px] font-semibold leading-[1.12] tracking-[-0.005em]">
            {job.title}
          </h3>
          {job.isNew && <Tag variant="new">NEW</Tag>}
          {job.status && job.status !== "Dismissed" && (
            <Tag variant="status">{job.status}</Tag>
          )}
        </div>
        <div className="mt-[6px] mb-[9px] flex flex-wrap items-center gap-[8px] text-[12.5px]">
          <span className="flex items-center gap-[6px] font-semibold">
            <span className="flex h-[18px] w-[18px] items-center justify-center rounded-[4px] bg-panel-2 font-mono text-[8.5px] font-semibold text-ink-2">
              {job.logo}
            </span>
            {job.company}
          </span>
          <span className="text-rule-2">/</span>
          <span className="text-ink-2">
            {job.flag} {job.city}
          </span>
          {!job.city.includes("Remote") && (
            <>
              <span className="text-rule-2">/</span>
              <span className="text-ink-2">{job.mode}</span>
            </>
          )}
          <span className="text-rule-2">/</span>
          <span className="text-ink-2">{job.seniority}</span>
          {job.salary && (
            <>
              <span className="text-rule-2">/</span>
              <span className="font-mono text-[11px] text-ink">
                {job.salary}
              </span>
            </>
          )}
        </div>
        <p className="m-0 mb-[10px] max-w-[62ch] text-[13px] leading-[1.5] text-ink-2 [text-wrap:pretty]">
          {job.rationale}
        </p>
        <div className="flex flex-wrap items-center gap-[14px] font-mono text-[10.5px] text-ink-2">
          <OverlapBar overlap={job.overlap} />
          <span className="tracking-[0.01em]">
            {job.stack.slice(0, 5).join(" · ")}
          </span>
          <span className={job.deadlineDays <= 7 ? "text-warn" : ""}>
            ↳ closes {job.deadlineDays}d
          </span>
          {job.redFlag && <Tag variant="flag">⚑ {job.redFlag}</Tag>}
          {!job.originVerified && <Tag variant="flag">⚐ origin unverified</Tag>}
        </div>
      </div>
      <MatchMeter job={job} mstyle="bars" replay={sig} countUp={!exit} />
    </article>
  );
}
```

- [ ] **Step 4: Add the FLIP + exit-row logic to JobsView**

Modify `apps/web/src/components/jobs/jobs-view.tsx`. Add imports `useLayoutEffect, useRef, useState` (extend the existing `useState` import) + `flipDelta` + `usePrefersReducedMotion`, and add the FLIP machinery. The full new file:

```tsx
"use client";

import { useLayoutEffect, useRef, useState } from "react";
import type { Job, JobSort, LensSummary, Candidate } from "@specula/shared-types";
import { scoredList } from "@/lib/jobs-scoring";
import { flipDelta } from "@/lib/flip";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";
import { LensBar } from "@/components/jobs/lens-bar";
import { JobRow } from "@/components/jobs/job-row";
import { JobDrawer } from "@/components/jobs/job-drawer";

type Pos = { top: number; left: number; width: number };
type Exit = { job: Job; top: number; left: number; width: number };

export function JobsView({
  pool,
  lenses,
  candidate,
}: {
  pool: Job[];
  lenses: LensSummary[];
  candidate: Candidate;
}) {
  const [lens, setLens] = useState("all");
  const [sort, setSort] = useState<JobSort>("match");
  const [selected, setSelected] = useState<Job | null>(null);
  const [exiting, setExiting] = useState<Exit[]>([]);
  const reduce = usePrefersReducedMotion();

  const list = scoredList(pool, lens, sort);
  const activeLens = lenses.find((l) => l.id === lens) ?? lenses[0];
  const closingSoon = list.filter(
    (j) => j.deadlineDays <= 7 && j.status !== "Applied",
  ).length;
  const newCount = pool.filter((j) => j.isNew).length;
  const sig = lens + "|" + sort;

  const listRef = useRef<HTMLDivElement>(null);
  const flip = useRef<{ pos: Map<string, Pos>; jobs: Map<string, Job>; init: boolean }>({
    pos: new Map(),
    jobs: new Map(),
    init: false,
  });

  // FLIP: on lens/sort change, fly surviving rows old→new and fade out leavers.
  useLayoutEffect(() => {
    const cont = listRef.current;
    if (!cont) return;
    const rows = Array.from(
      cont.querySelectorAll<HTMLElement>("article[data-fid]:not([data-exit])"),
    );
    const newPos = new Map<string, Pos>();
    rows.forEach((n) =>
      newPos.set(n.dataset.fid!, {
        top: n.offsetTop,
        left: n.offsetLeft,
        width: n.offsetWidth,
      }),
    );
    const newJobs = new Map(list.map((j) => [j.id, j]));
    if (flip.current.init && !reduce) {
      rows.forEach((n) => {
        const prev = flip.current.pos.get(n.dataset.fid!);
        const next = newPos.get(n.dataset.fid!);
        if (!prev || !next) return;
        const d = flipDelta(prev, next);
        if (d) {
          n.animate(
            [{ transform: `translate(${d.dx}px, ${d.dy}px)` }, { transform: "none" }],
            { duration: 560, easing: "cubic-bezier(.3,.9,.3,1)" },
          );
        }
      });
      const exits: Exit[] = [];
      flip.current.pos.forEach((p, id) => {
        if (!newPos.has(id)) {
          const j = flip.current.jobs.get(id);
          if (j) exits.push({ job: j, ...p });
        }
      });
      if (exits.length) {
        setExiting(exits);
        setTimeout(() => setExiting([]), 480);
      }
    }
    flip.current.pos = newPos;
    flip.current.jobs = newJobs;
    flip.current.init = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  return (
    <section
      data-screen-label="jobs"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16 motion-safe:[animation:viewIn_0.4s_cubic-bezier(0.2,0.7,0.2,1)]"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Jobs
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            One shared, deduped pool. Role &amp; skill fit are scored against
            your targeting and candidate profile; the{" "}
            <b>location factor re-scores per lens</b>, so switching a lens
            genuinely re-ranks the pool — not just filters it.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">{pool.length}</b>{" "}
            in pool
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{newCount}</b> new
          </div>
        </div>
      </header>

      <LensBar lenses={lenses} active={lens} onSelect={setLens} />

      {closingSoon > 0 && (
        <div className="mt-[18px] flex items-center gap-[12px] rounded-[11px] border border-warn bg-warn-bg px-[18px] py-[13px] text-[13px] text-warn">
          ⏱{" "}
          <span>
            <b className="font-semibold">
              {closingSoon} {closingSoon === 1 ? "role" : "roles"}
            </b>{" "}
            in this lens close within 7 days — review before they disappear from
            the feed.
          </span>
        </div>
      )}

      <div className="mt-[16px] mb-[6px] flex items-center justify-between font-mono text-[11px] text-ink-2">
        <div className="flex items-center gap-[14px]">
          <span className="text-ink">{activeLens.scope}</span>
          <span>· {activeLens.modes.join(" / ")}</span>
          <span>· {activeLens.origin}</span>
          {lens !== "all" && (
            <span className="text-accent-ink">
              · ◉ match re-scored for this lens
            </span>
          )}
        </div>
        <div className="flex items-center gap-[9px]">
          <span>sort</span>
          <select
            aria-label="sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as JobSort)}
            className="rounded-[6px] border border-rule-2 px-[9px] py-[5px] font-mono text-[11px] text-ink"
          >
            <option value="match">match index ↓</option>
            <option value="deadline">deadline ↑</option>
            <option value="new">newest</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-[30px_1fr_248px] gap-[18px] border-b border-rule pt-[14px] pb-[9px] font-mono text-[9.5px] uppercase tracking-[0.08em] text-ink-3">
        <span>#</span>
        <span>role / source / facts</span>
        <span>match · role / skill / loc</span>
      </div>

      <div className="relative" ref={listRef}>
        {list.length === 0 && (
          <div className="px-[20px] py-[80px] text-center text-ink-2">
            <div className="mb-[14px] text-[34px] opacity-40">⬚</div>
            No roles in this lens yet. Discovery runs weekly — or trigger a
            refresh.
          </div>
        )}
        {list.map((j, i) => (
          <JobRow key={j.id} job={j} i={i} onOpen={setSelected} sig={sig} />
        ))}
        {exiting.map((e) => (
          <JobRow
            key={"x" + e.job.id}
            job={e.job}
            i={0}
            onOpen={setSelected}
            sig={sig}
            exit
            style={{ position: "absolute", top: e.top, left: e.left, width: e.width }}
          />
        ))}
      </div>

      {selected && (
        <JobDrawer
          job={selected}
          candidate={candidate}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 5: Extend the JobRow unit test — the `sig`/`exit` props render safely**

Append to `apps/web/src/components/jobs/job-row.test.tsx` (inside the existing `describe`), and update the EXISTING tests' `<JobRow .../>` usages to pass `sig="all|match"` (the prop is now required):

```tsx
  it("renders an exit row (non-interactive, positioned) without crashing", () => {
    const onOpen = vi.fn();
    const { container } = render(
      <JobRow job={base} i={0} onOpen={onOpen} sig="all|match" exit style={{ top: 5 }} />,
    );
    const article = container.querySelector("article[data-fid]")!;
    expect(article.getAttribute("data-exit")).toBe("");
    // exit rows don't open the drawer
    fireEvent.click(article);
    expect(onOpen).not.toHaveBeenCalled();
  });
```

- [ ] **Step 6: Run tests to verify green**

Run: `pnpm test src/components/jobs/job-row.test.tsx`
Expected: PASS (existing tests updated with `sig`, + the new exit test).

- [ ] **Step 7: Run gates + the FLIP E2E**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Then: `pnpm exec playwright test --project=authed e2e/authed/flip.spec.ts`
Expected: green — lens switch re-sorts, row set changes, meters present.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/jobs/jobs-view.tsx apps/web/src/components/jobs/job-row.tsx apps/web/src/components/jobs/job-row.test.tsx apps/web/e2e/authed/flip.spec.ts
git commit -m "feat(web): FLIP lens re-sort + row entrance/exit + meter replay (M1c)"
```

---

### Task 5: Row → drawer morph + scoring reveal

**Files:**
- Modify: `apps/web/src/components/jobs/job-row.tsx` (rect capture), `apps/web/src/components/jobs/jobs-view.tsx` (morphFrom state), `apps/web/src/components/jobs/job-drawer.tsx` (morph + reveal + close fallback)
- Test: `apps/web/src/components/jobs/job-drawer.test.tsx` (extend), `apps/web/e2e/authed/morph.spec.ts`

**Interfaces:**
- Consumes: `morphScale` + `usePrefersReducedMotion` (Task 1).
- Produces:
  - `MorphRects = { title: DOMRect; titleFont: number; meter: DOMRect }` (a shared type).
  - `JobRow.onOpen: (job: Job, rects: MorphRects) => void`.
  - `JobDrawer({ job, candidate, onClose, morphFrom?: MorphRects })`.

- [ ] **Step 1: Write the failing morph E2E**

Create `apps/web/e2e/authed/morph.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("clicking a job row opens the drawer with the same title; Esc closes it", async ({
  page,
}) => {
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("specula_intro", "1"); // skip intro
    } catch {}
  });
  await page.goto("/jobs");
  const firstRow = page.locator("article[data-fid]").first();
  await expect(firstRow).toBeVisible();
  const title = await firstRow.getByRole("heading", { level: 3 }).innerText();
  await firstRow.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { level: 2, name: title })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm exec playwright test --project=authed e2e/authed/morph.spec.ts`
Expected: FAIL — the current drawer closes on Esc but the morph capture path isn't wired; run after Step 5 to confirm green. (It may pass structurally since M1b already opens the drawer + Esc-closes; this is the regression guard for the morph version.)

- [ ] **Step 3: Add rect capture to JobRow's click**

In `apps/web/src/components/jobs/job-row.tsx`: import `useRef`, change `onOpen` to `(job: Job, rects: MorphRects) => void`, add a `MorphRects` type import, a `ref` on the `<article>`, and measure the title `<h3>` + meter on click. Add `import { useRef } from "react";` and `import type { MorphRects } from "@/components/jobs/morph";` at the top, mark the file `"use client"` (it now uses a hook), give the `<h3>` a `data-jtitle` attribute and wrap `<MatchMeter>` in a `<div data-meter>`, and replace the `onClick`:

```tsx
  const ref = useRef<HTMLElement>(null);
  const open = () => {
    if (exit) return;
    const root = ref.current;
    if (!root) return;
    const titleEl = root.querySelector<HTMLElement>("[data-jtitle]");
    const meterEl = root.querySelector<HTMLElement>("[data-meter]");
    if (!titleEl || !meterEl) return;
    onOpen(job, {
      title: titleEl.getBoundingClientRect(),
      titleFont: parseFloat(getComputedStyle(titleEl).fontSize),
      meter: meterEl.getBoundingClientRect(),
    });
  };
```

Set `ref={ref}` on the `<article>`, change its `onClick` to `onClick={open}`, add `data-jtitle` to the `<h3>`, and wrap the meter: `<div data-meter><MatchMeter job={job} mstyle="bars" replay={sig} countUp={!exit} /></div>`.

Create `apps/web/src/components/jobs/morph.ts`:

```ts
export type MorphRects = {
  title: DOMRect;
  titleFont: number;
  meter: DOMRect;
};
```

**Also update the existing JobRow unit test** (`job-row.test.tsx`): the M1b-1 test `"calls onOpen with the job when clicked"` asserts `expect(onOpen).toHaveBeenCalledWith(base)`, but `onOpen` now receives a second `rects` argument. Change that assertion to:

```tsx
    expect(onOpen).toHaveBeenCalledWith(base, expect.objectContaining({ title: expect.anything() }));
```

(In jsdom, `getBoundingClientRect()` returns a zero DOMRect and `getComputedStyle().fontSize` may be empty → `titleFont: NaN`; the test only asserts the rects object was passed, so this is fine. The `data-jtitle`/`data-meter` elements exist in the render, so `open()` proceeds.)

- [ ] **Step 4: Thread `morphFrom` through JobsView**

In `apps/web/src/components/jobs/jobs-view.tsx`: add `const [morphFrom, setMorphFrom] = useState<MorphRects | null>(null);` (import the type), change the row handlers so opening captures rects and closing clears them:
- the `onOpen` passed to rows becomes `(job, rects) => { setSelected(job); setMorphFrom(rects); }` — define `const openJob = (job: Job, rects: MorphRects) => { setSelected(job); setMorphFrom(rects); };` and pass `onOpen={openJob}` to the live rows. For the **exit** rows pass a no-op-safe `onOpen={openJob}` too (exit rows ignore clicks internally).
- the drawer: `<JobDrawer job={selected} candidate={candidate} morphFrom={morphFrom} onClose={() => { setSelected(null); setMorphFrom(null); }} />`.

- [ ] **Step 5: Add morph + reveal + close-fallback to JobDrawer (from `jobs.jsx:129-186`)**

Replace `apps/web/src/components/jobs/job-drawer.tsx`. The header `<h2>` and the Match-section meter get refs; a `useLayoutEffect` runs the morph (or plain slide when no `morphFrom`/reduced-motion); close animates out with a `setTimeout` fallback; the `MatchMeter` reveals when there's no morph:

```tsx
"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Job, Candidate } from "@specula/shared-types";
import type { MorphRects } from "@/components/jobs/morph";
import { morphScale } from "@/lib/flip";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Tag } from "@/components/atoms/tag";
import { Button } from "@/components/atoms/button";
import {
  Section,
  InsightRecord,
  SkillsSplit,
  Lifecycle,
  Feedback,
} from "@/components/jobs/drawer-sections";

export function JobDrawer({
  job,
  candidate,
  onClose,
  morphFrom = null,
}: {
  job: Job;
  candidate: Candidate;
  onClose: () => void;
  morphFrom?: MorphRects | null;
}) {
  const reduce = usePrefersReducedMotion();
  const panelRef = useRef<HTMLElement>(null);
  const scrimRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const meterRef = useRef<HTMLDivElement>(null);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useLayoutEffect(() => {
    const panel = panelRef.current;
    const scrim = scrimRef.current;
    if (!panel) return;
    if (scrim) scrim.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, easing: "ease" });
    if (reduce) return;
    if (morphFrom) {
      panel.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 240, easing: "ease" });
      const morph = (
        el: HTMLElement | null,
        src: DOMRect,
        srcFont: number | null,
        delay: number,
      ) => {
        if (!el) return;
        const d = el.getBoundingClientRect();
        const dx = src.left - d.left;
        const dy = src.top - d.top;
        const s = srcFont
          ? morphScale(srcFont, parseFloat(getComputedStyle(el).fontSize))
          : morphScale(src.width, d.width);
        el.animate(
          [
            { transform: `translate(${dx}px, ${dy}px) scale(${s})`, opacity: 0.55 },
            { transform: "none", opacity: 1 },
          ],
          { duration: 540, delay, easing: "cubic-bezier(.4,0,.12,1)", fill: "backwards" },
        );
      };
      morph(titleRef.current, morphFrom.title, morphFrom.titleFont, 0);
      morph(meterRef.current, morphFrom.meter, null, 40);
    } else {
      panel.animate([{ transform: "translateX(100%)" }, { transform: "none" }], {
        duration: 440,
        easing: "cubic-bezier(.3,.9,.3,1)",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleClose = () => {
    if (closing) return;
    const panel = panelRef.current;
    const scrim = scrimRef.current;
    if (reduce || !panel) {
      onClose();
      return;
    }
    setClosing(true);
    if (scrim)
      scrim.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 260, easing: "ease", fill: "forwards" });
    const a = panel.animate(
      [
        { transform: "none", opacity: 1 },
        { transform: "translateX(46px)", opacity: 0 },
      ],
      { duration: 300, easing: "cubic-bezier(.4,0,.7,1)", fill: "forwards" },
    );
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        onClose();
      }
    };
    a.onfinish = finish;
    setTimeout(finish, 360);
  };

  return (
    <>
      <div
        ref={scrimRef}
        onClick={handleClose}
        className="fixed inset-0 z-40 bg-[rgba(33,30,24,0.28)] backdrop-blur-[2px]"
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        className="fixed inset-y-0 right-0 z-[41] w-[560px] max-w-[94vw] overflow-y-auto border-l border-rule-2 bg-paper shadow-pop"
      >
        <div className="sticky top-0 z-[2] border-b border-rule bg-paper px-[28px] pt-[22px] pb-[18px]">
          <button
            onClick={handleClose}
            aria-label="Close"
            className="absolute right-[22px] top-[18px] flex h-[30px] w-[30px] items-center justify-center rounded-[7px] border border-rule-2 bg-card text-[16px] text-ink-2 hover:border-ink hover:text-ink"
          >
            ✕
          </button>
          <div className="mb-[10px] flex items-center gap-[9px] font-mono text-[11px] text-ink-2">
            <span className="flex h-[18px] w-[18px] items-center justify-center rounded-[4px] bg-panel-2 font-mono text-[8.5px] font-semibold text-ink-2">
              {job.logo}
            </span>
            {job.company}
            <span className="text-rule-2">/</span>
            {job.flag} {job.city} · {job.mode}
            {job.isNew && (
              <span className="ml-1">
                <Tag variant="new">NEW</Tag>
              </span>
            )}
          </div>
          <h2
            ref={titleRef}
            className="m-0 mr-[56px] mb-[8px] origin-top-left font-display text-[25px] font-semibold leading-[1.12] tracking-[-0.01em]"
          >
            {job.title}
          </h2>
          <div className="flex flex-wrap items-center gap-[8px] text-[13px] text-ink-2">
            <span>{job.seniority}</span>
            <span className="text-rule-2">·</span>
            <span>{job.contract}</span>
            <span className="text-rule-2">·</span>
            <span className="font-mono">posted {job.posted}</span>
          </div>
        </div>

        <div className="px-[28px] pt-[24px] pb-[60px]">
          <Section>
            <div className="mb-[16px] flex items-start gap-[22px]">
              <div ref={meterRef} className="origin-top-left">
                <MatchMeter job={job} mstyle="bars" reveal={!morphFrom} replay={job.id} />
              </div>
            </div>
            <p className="max-w-none text-[13.5px] leading-[1.5] text-ink-2">
              {job.rationale}
            </p>
            <div className="mt-[4px] flex flex-wrap items-center gap-[14px] font-mono text-[10.5px] text-ink-2">
              <OverlapBar overlap={job.overlap} />
              <span className={job.deadlineDays <= 7 ? "text-warn" : ""}>
                ↳ closes in {job.deadlineDays} days
              </span>
            </div>
          </Section>

          <Section head="summary">
            <p className="text-[14.5px] leading-[1.6] text-ink [text-wrap:pretty]">
              {job.summary}
            </p>
          </Section>

          <Section
            head="skills · required vs your profile"
            note={`${job.overlap[0]} of ${job.overlap[1]} matched`}
          >
            <SkillsSplit job={job} candidate={candidate} />
          </Section>

          <Section head="insight record" note="extracted · cached">
            <InsightRecord job={job} />
          </Section>

          <Section head="responsibilities">
            <ul className="m-0 list-disc pl-[18px] text-[13.5px] leading-[1.7] text-ink">
              {job.responsibilities.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Section>

          <Section head="application status">
            <Lifecycle
              status={
                job.status && job.status !== "Dismissed" ? job.status : null
              }
              note=""
            />
          </Section>

          <Section head="feedback" note="steers your recommender">
            <Feedback />
          </Section>

          <div className="flex gap-[10px]">
            <Button variant="pri" className="flex-1 justify-center">
              ↗ Open posting
            </Button>
            <Button>★ Save</Button>
          </div>
        </div>
      </aside>
    </>
  );
}
```

- [ ] **Step 6: Update the JobDrawer unit test — reveal wiring + morphFrom optional**

The existing `job-drawer.test.tsx` renders `<JobDrawer job candidate onClose>` with no `morphFrom` — that path now plays the reveal (`reveal={!morphFrom}` → true). The tests assert sections + close; they still pass (jsdom stubs `.animate()`). Add one assertion that the drawer renders the meter in reveal state (no `morphFrom`):

```tsx
  it("reveals the MatchMeter when opened without a morph (no rects)", () => {
    render(<JobDrawer job={job} candidate={candidate} onClose={() => {}} />);
    // reveal mode shows the "scoring…" label initially (MatchMeter reveal)
    expect(screen.getByText(/scoring/i)).toBeInTheDocument();
  });
```

- [ ] **Step 7: Run tests to verify green**

Run: `pnpm test src/components/jobs/job-drawer.test.tsx`
Expected: PASS (existing + the reveal assertion). `element.animate` is a jsdom no-op stub, so the WAAPI calls don't throw.

- [ ] **Step 8: Run gates + the morph E2E**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Then: `pnpm exec playwright test --project=authed e2e/authed/morph.spec.ts`
Expected: green — row click opens the drawer with the matching title; Esc closes.

- [ ] **Step 9: Commit**

```bash
git add apps/web/src/components/jobs/job-row.tsx apps/web/src/components/jobs/jobs-view.tsx apps/web/src/components/jobs/job-drawer.tsx apps/web/src/components/jobs/morph.ts apps/web/src/components/jobs/job-drawer.test.tsx apps/web/e2e/authed/morph.spec.ts
git commit -m "feat(web): row→drawer shared-element morph + scoring reveal + close fallback (M1c)"
```

---

### Task 6: Insights entrances (bar-grow + count-up) + build gate

**Files:**
- Create: `apps/web/src/components/insights/count-up.tsx`
- Test: `apps/web/src/components/insights/count-up.test.tsx`
- Modify: `apps/web/src/components/insights/insights-view.tsx` (bar-grow class + `<CountUp>`)

**Interfaces:**
- Consumes: `useCountUp` + `usePrefersReducedMotion` (Task 1).
- Produces: `CountUp({ value: number, dur?: number })` — `"use client"`; counts up from 0 to `value` (immediate under reduced-motion).

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/insights/count-up.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { CountUp } from "@/components/insights/count-up";

afterEach(cleanup);

describe("CountUp", () => {
  it("shows the final value immediately under reduced motion", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: true, // prefers-reduced-motion: reduce
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    render(<CountUp value={312} />);
    expect(screen.getByText("312")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm test src/components/insights/count-up.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement CountUp**

Create `apps/web/src/components/insights/count-up.tsx`:

```tsx
"use client";

import { useCountUp } from "@/lib/use-count-up";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

export function CountUp({ value, dur = 900 }: { value: number; dur?: number }) {
  const reduce = usePrefersReducedMotion();
  const shown = useCountUp(value, !reduce, dur);
  return <>{reduce ? value : shown}</>;
}
```

- [ ] **Step 4: Wire CountUp + bar-grow into InsightsView**

In `apps/web/src/components/insights/insights-view.tsx`:
- add `import { CountUp } from "@/components/insights/count-up";` at the top;
- replace the analysed total `{ins.totalAnalysed}` (in the header `<b>`) with `<CountUp value={ins.totalAnalysed} />`;
- on each bar **fill** span (the inner `<span className="block h-full rounded-[3px] ...">` in Skill demand, Seniority mix, Most-active companies) add `origin-left motion-safe:[animation:barGrow_0.9s_cubic-bezier(0.3,1,0.3,1)]` to its className (the width stays inline; the scaleX keyframe grows it from 0 → its set width, disabled under reduced motion).

Example — the Skill-demand fill becomes:

```tsx
                  <span
                    className={`block h-full origin-left rounded-[3px] motion-safe:[animation:barGrow_0.9s_cubic-bezier(0.3,1,0.3,1)] ${s.up ? "bg-accent" : "bg-ink"}`}
                    style={{ width: `${s.pct}%` }}
                  />
```

Apply the same `origin-left motion-safe:[animation:barGrow_...]` addition to the Seniority-mix and Most-active-companies fill spans. (Leave the mixbar, salary bars, and trend segments as-is — they animate in M1d's polish if desired; scope here is the three horizontal bar groups + the count-up.)

- [ ] **Step 5: Run test + gates + BUILD**

Run: `pnpm test src/components/insights/count-up.test.tsx`
Expected: PASS.
Then run the full gate set INCLUDING BUILD from `apps/web`:
`pnpm test && pnpm lint && pnpm typecheck && pnpm format:check && pnpm build`
**The build is a required gate for this task.** If it hits a TLS `SELF_SIGNED_CERT_IN_CHAIN` error, re-run as `NODE_EXTRA_CA_CERTS="$HOME/.corp-ca.pem" pnpm build`.

- [ ] **Step 6: Run the full authed E2E suite (all four moments)**

Run: `pnpm test:e2e`
Expected: all green — `public` (unauth redirects) + `authed` (smoke, intro, flip, morph).

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/insights/count-up.tsx apps/web/src/components/insights/count-up.test.tsx apps/web/src/components/insights/insights-view.tsx
git commit -m "feat(web): Insights bar-grow entrance + analysed count-up (M1c)"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** Task 1 → §1.1 foundation + the M1b-1 dedup + §2 architecture (hook/keyframes). Task 2 → §1.2 E2E harness (two servers). Task 3 → §4.1 assembling intro (derived counts, once-per-session, reduced-motion). Task 4 → §4.2 FLIP + §5 row/view entrances. Task 5 → §4.3 reveal + §4.4 morph (close fallback, clamp via `morphScale`). Task 6 → §5 Insights entrances + the build gate. Reduced-motion is present in every task (hook + `motion-safe:` + `@media`).
- **Type consistency:** `scoredList`/`flipDelta`/`morphScale`/`usePrefersReducedMotion` (Task 1) are consumed verbatim in Tasks 3–6. `MorphRects` (Task 5) flows JobRow→JobsView→JobDrawer. `JobRow` gains `sig` in Task 4 (all call sites updated) and rect-capture in Task 5. `MatchMeter` `reveal`/`replay`/`countUp` props are already on the M1a atom.
- **The FLIP/morph are jsdom-safe:** `element.animate` is a jsdom no-op, so unit tests don't throw; the real motion is E2E-verified (Tasks 4–5) + my browser drive.
- **E2E stability:** authed specs assert stable end-states (drawer open, set changed, intro hidden) — not mid-frames. The two-server split keeps the existing unauth-redirect specs green.
- **No new E2E on a prod build:** authed E2E runs on `next dev` + the bypass (dev-only gate intact).
- **After Task 6:** I (the controller) verify all four moments in a real browser via `just dev-web-noauth` before the final review, since motion is the point.
