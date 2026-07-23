# Targeting Page Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/targeting` fully editable and persistent — wire save (dirty-state), make seniority an editable multi-select over a canonical ladder, control the preferences textarea, and add role-title suggestions.

**Architecture:** Frontend-only completion — the backend `GET`/`PUT /targeting` and the `targeting` table already exist and are untouched. Generalize the candidate `ModeSelect` into a reusable `ChipMultiSelect` (used by seniority; `ModeSelect` delegates to it), reuse `TagEditor`'s `suggestions` prop and the candidate-view dirty-state save pattern. `Targeting.seniority` becomes `Seniority[]`; `getTargeting` sanitizes legacy/out-of-ladder reads.

**Tech Stack:** Next 16 · React 19 · TypeScript strict · Tailwind · Vitest + Testing Library (`apps/web`); shared TS types in `packages/shared-types`. No `apps/api` changes.

## Global Constraints

- **No backend change.** `GET`/`PUT /targeting`, `TargetingIn`/`TargetingOut`, the `targeting` table, and `upsert_targeting` (which re-embeds nothing) are untouched. `seniority` stays `list[str]` server-side.
- **Seniority is constrained on the frontend only.** The multi-select limits input; `getTargeting` sanitizes reads to the ladder. No backend `Literal` (that would reintroduce the read-500 bug fixed on the candidate page).
- **Seniority ladder (exact, ordered):** `Junior`, `Mid`, `Senior`, `Staff`, `Principal`, `Lead`, `Manager`, `Director`.
- **Enum source of truth:** `SENIORITY_LEVELS` in `packages/shared-types/src/index.ts`. The `ROLE_TITLES` catalog is a **frontend-only** suggestion list (free-add always accepted; no server constraint).
- **No geography or salary** on this page (spec invariant) — preserve the existing header copy and the invariant banner verbatim.
- **Reuse, don't reinvent:** `TagEditor` (with `suggestions`), the dirty-state save pattern from `candidate-view.tsx`, and the generalized `ChipMultiSelect`.
- **Run commands:** `just typecheck` (mypy + tsc), `just test` (pytest + vitest), `just lint`. Single web test: `cd apps/web && pnpm vitest run <path>`. Web typecheck: `cd apps/web && pnpm typecheck`; shared-types: `cd packages/shared-types && pnpm typecheck`.
- **Next 16 is not the Next you know** (`apps/web/AGENTS.md`) — this plan uses only client components and no new Next APIs.

---

### Task 1: Shared `Seniority` type + `SENIORITY_LEVELS` + role-titles catalog

Additive — does **not** change the `Targeting` interface yet (that flip is Task 4), so `pnpm typecheck` stays green.

**Files:**
- Modify: `packages/shared-types/src/index.ts`
- Create: `apps/web/src/lib/role-titles-catalog.ts`

**Interfaces:**
- Produces: `Seniority` (type), `SENIORITY_LEVELS` (runtime array), `ROLE_TITLES: string[]`.

- [ ] **Step 1: Add the seniority type + ladder to shared-types**

Insert immediately **above** the existing `export interface Targeting {` line in `packages/shared-types/src/index.ts`:

```ts
export type Seniority =
  | "Junior"
  | "Mid"
  | "Senior"
  | "Staff"
  | "Principal"
  | "Lead"
  | "Manager"
  | "Director";
export const SENIORITY_LEVELS: readonly Seniority[] = [
  "Junior",
  "Mid",
  "Senior",
  "Staff",
  "Principal",
  "Lead",
  "Manager",
  "Director",
];
```

- [ ] **Step 2: Create the role-titles catalog**

Create `apps/web/src/lib/role-titles-catalog.ts`:

```ts
// Frontend-only suggestion list for the Role-titles typeahead (a <datalist>). NOT a
// server constraint — any typed value is still accepted (free-add). Helps capture the
// synonyms a posting's title might use, which feeds the role-match factor.
export const ROLE_TITLES: string[] = [
  "Data Scientist",
  "Senior Data Scientist",
  "Machine Learning Engineer",
  "ML Engineer",
  "Senior ML Engineer",
  "Staff Machine Learning Engineer",
  "AI Engineer",
  "AI Developer",
  "Applied Scientist",
  "Research Engineer",
  "Research Scientist",
  "Machine Learning Researcher",
  "Deep Learning Engineer",
  "MLOps Engineer",
  "ML Platform Engineer",
  "Data Engineer",
  "Analytics Engineer",
  "NLP Engineer",
  "Computer Vision Engineer",
  "LLM Engineer",
  "Applied ML Engineer",
  "AI Research Scientist",
  "Software Engineer, Machine Learning",
  "Data Science Manager",
  "Head of Machine Learning",
];
```

- [ ] **Step 3: Verify typecheck passes**

Run: `cd apps/web && pnpm typecheck`
Expected: exits 0 (additions only).

- [ ] **Step 4: Commit**

```bash
git add packages/shared-types/src/index.ts apps/web/src/lib/role-titles-catalog.ts
git commit -m "feat(targeting): add Seniority type/ladder + role-titles catalog"
```

---

### Task 2: `ChipMultiSelect` reusable component

**Files:**
- Create: `apps/web/src/components/atoms/chip-multi-select.tsx`
- Test: `apps/web/src/components/atoms/chip-multi-select.test.tsx`

**Interfaces:**
- Produces: `<ChipMultiSelect<T extends string> options={readonly T[]} value={T[]} onChange={(v: T[]) => void} />` — chip toggles; `aria-pressed` reflects selection; click toggles an option in/out of `value`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/atoms/chip-multi-select.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";

afterEach(cleanup);
const OPTS = ["A", "B", "C"] as const;

describe("ChipMultiSelect", () => {
  it("reflects selection via aria-pressed", () => {
    render(<ChipMultiSelect options={OPTS} value={["A"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "A" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "B" })).toHaveAttribute("aria-pressed", "false");
  });

  it("adds an option when an off chip is clicked", () => {
    const onChange = vi.fn();
    render(<ChipMultiSelect options={OPTS} value={["A"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith(["A", "B"]);
  });

  it("removes an option when an on chip is clicked", () => {
    const onChange = vi.fn();
    render(<ChipMultiSelect options={OPTS} value={["A", "B"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "A" }));
    expect(onChange).toHaveBeenCalledWith(["B"]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/atoms/chip-multi-select.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/atoms/chip-multi-select.tsx`:

```tsx
"use client";

export function ChipMultiSelect<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T[];
  onChange: (v: T[]) => void;
}) {
  const toggle = (o: T) =>
    onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o]);

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button
            key={o}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(o)}
            className={`rounded-[8px] border px-[15px] py-[10px] text-[12.5px] transition-colors ${
              on
                ? "border-ink bg-ink text-paper"
                : "border-rule-2 bg-panel text-ink hover:border-ink"
            }`}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/atoms/chip-multi-select.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/atoms/chip-multi-select.tsx apps/web/src/components/atoms/chip-multi-select.test.tsx
git commit -m "feat(atoms): ChipMultiSelect reusable chip-toggle multi-select"
```

---

### Task 3: Refactor `ModeSelect` to delegate to `ChipMultiSelect`

**Files:**
- Modify: `apps/web/src/components/candidate/mode-select.tsx`

**Interfaces:**
- Consumes: `ChipMultiSelect` (Task 2). `ModeSelect`'s public signature (`value: Mode[]`, `onChange: (v: Mode[]) => void`) is unchanged — candidate-view is untouched.

- [ ] **Step 1: Replace the implementation with delegation**

Replace the entire contents of `apps/web/src/components/candidate/mode-select.tsx` with:

```tsx
"use client";

import type { Mode } from "@specula/shared-types";
import { WORK_MODES } from "@specula/shared-types";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";

export function ModeSelect({
  value,
  onChange,
}: {
  value: Mode[];
  onChange: (v: Mode[]) => void;
}) {
  return <ChipMultiSelect options={WORK_MODES} value={value} onChange={onChange} />;
}
```

- [ ] **Step 2: Run the guarding tests (ModeSelect + its consumer)**

Run: `cd apps/web && pnpm vitest run src/components/candidate/mode-select.test.tsx src/components/candidate/candidate-view.test.tsx`
Expected: PASS — the existing `ModeSelect` tests (3) and `CandidateView` tests still pass, confirming the refactor preserved behavior.

- [ ] **Step 3: Typecheck**

Run: `cd apps/web && pnpm typecheck`
Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/candidate/mode-select.tsx
git commit -m "refactor(candidate): ModeSelect delegates to ChipMultiSelect"
```

---

### Task 4: Integration — persistence, seniority multi-select, controlled preferences, role-title suggestions

The atomic swap: change `Targeting.seniority`, wire the client + BFF, and rewrite the view together so typecheck and Vitest end green.

**Files:**
- Modify: `packages/shared-types/src/index.ts` (`Targeting.seniority` → `Seniority[]`)
- Modify: `apps/web/src/lib/api/targeting.ts` (mapping + `saveTargeting`)
- Modify: `apps/web/src/app/api/targeting/route.ts` (add `PUT`)
- Modify: `apps/web/src/components/targeting/targeting-view.tsx` (rewrite)
- Modify: `apps/web/src/components/targeting/targeting-view.test.tsx`
- Verify: `apps/web/src/lib/seed/data.ts` + `apps/web/src/lib/api/test-fixtures.ts` compile unchanged (seed seniority `["Mid","Senior","Staff"]` are all valid `Seniority`)

**Interfaces:**
- Consumes: `ChipMultiSelect` (Task 2), `SENIORITY_LEVELS`/`Seniority` + `ROLE_TITLES` (Task 1), `TagEditor` `suggestions` (already built).

- [ ] **Step 1: Change the `Targeting` interface**

In `packages/shared-types/src/index.ts`, replace the existing `Targeting` interface with (only `seniority`'s type changes):

```ts
export interface Targeting {
  roleTitles: string[]; seniority: Seniority[]; mustHaves: string[];
  avoid: string[]; preferences: string;
}
```

- [ ] **Step 2: Update the client mapping (`targeting.ts`)**

Replace the entire contents of `apps/web/src/lib/api/targeting.ts` with:

```ts
import type { Seniority, Targeting } from "@specula/shared-types";
import { SENIORITY_LEVELS } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// FastAPI's `TargetingOut` (camelCased). `seniority` is lenient server-side
// (`list[str]`) and is sanitized to the canonical ladder below.
type TargetingApiOut = {
  roleTitles: string[];
  seniority: string[];
  mustHaves: string[];
  avoid: string[];
  preferences: string | null;
};

export async function getTargeting(): Promise<Targeting> {
  const api = await bffFetch<TargetingApiOut>("/targeting");
  return {
    roleTitles: api.roleTitles,
    // drop legacy / out-of-ladder seniority values so the multi-select gets valid input
    seniority: api.seniority.filter((s): s is Seniority =>
      (SENIORITY_LEVELS as readonly string[]).includes(s),
    ),
    mustHaves: api.mustHaves,
    avoid: api.avoid,
    preferences: api.preferences ?? "",
  };
}

// The whole targeting form is editable; the patch is the full contract.
export type TargetingPatch = Targeting;

// Client-side: persist through the BFF route (which proxies to FastAPI
// `PUT /targeting`, a full replace).
export async function saveTargeting(patch: TargetingPatch): Promise<void> {
  const res = await fetch("/api/targeting", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      roleTitles: patch.roleTitles,
      seniority: patch.seniority,
      mustHaves: patch.mustHaves,
      avoid: patch.avoid,
      preferences: patch.preferences,
    }),
  });
  if (!res.ok) throw new Error(`Failed to save targeting (${res.status})`);
}
```

- [ ] **Step 3: Add the BFF `PUT` route**

Replace the entire contents of `apps/web/src/app/api/targeting/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getTargeting } from "@/lib/api/targeting";
import { bffFetch } from "@/lib/api/bff";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getTargeting());
}

export async function PUT(request: Request): Promise<NextResponse> {
  const body = await request.json();
  const updated = await bffFetch("/targeting", {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return NextResponse.json(updated);
}
```

- [ ] **Step 4: Update the TargetingView tests**

Replace the entire contents of `apps/web/src/components/targeting/targeting-view.test.tsx` with:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { TargetingView } from "@/components/targeting/targeting-view";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getTargeting } = await import("@/lib/api/targeting");

afterEach(cleanup);
const t = await getTargeting();

describe("TargetingView", () => {
  it("renders tag fields, seniority toggles, preferences, and the invariant banner", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getByText(t.roleTitles[0])).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.seniority[0] })).toBeInTheDocument();
    expect(screen.getByDisplayValue(t.preferences)).toBeInTheDocument();
    expect(screen.getByText(/never a rule or signal/)).toBeInTheDocument();
  });

  it("has three tag editors (role titles, must-haves, avoid)", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getAllByText("+ add")).toHaveLength(3);
  });

  it("gates Save on dirty state and toggles seniority", () => {
    render(<TargetingView targeting={t} />);
    const save = screen.getByText("Save targeting");
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Principal" })); // not in seed seniority
    expect(save).not.toBeDisabled();
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("adds a role title via the suggestions input (free-add)", () => {
    render(<TargetingView targeting={t} />);
    fireEvent.click(screen.getAllByText("+ add")[0]); // first TagEditor = role titles
    const input = document.activeElement as HTMLInputElement;
    expect(input).toHaveAttribute("list"); // suggestions datalist wired
    fireEvent.change(input, { target: { value: "LLM Engineer" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByText("LLM Engineer")).toBeInTheDocument();
  });

  it("Save targeting PUTs the edited fields through the BFF route", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    render(<TargetingView targeting={t} />);
    fireEvent.click(screen.getByRole("button", { name: "Principal" }));
    fireEvent.click(screen.getByText("Save targeting"));
    await screen.findByText("Saved.");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/targeting",
      expect.objectContaining({ method: "PUT" }),
    );
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init!.body as string);
    expect(body.seniority).toContain("Principal");
    fetchMock.mockRestore();
  });
});
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd apps/web && pnpm vitest run src/components/targeting/targeting-view.test.tsx`
Expected: FAIL — the current view has no "Save targeting" button, no seniority toggles (renders read-only chips), and role titles have no `list` attr.

- [ ] **Step 6: Rewrite `targeting-view.tsx`**

Replace the entire contents of `apps/web/src/components/targeting/targeting-view.tsx` with:

```tsx
"use client";

import { useMemo, useState } from "react";
import type { Targeting } from "@specula/shared-types";
import { SENIORITY_LEVELS } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Button } from "@/components/atoms/button";
import { Field } from "@/components/config/field";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";
import { ROLE_TITLES } from "@/lib/role-titles-catalog";
import { saveTargeting, type TargetingPatch } from "@/lib/api/targeting";

export function TargetingView({ targeting: t }: { targeting: Targeting }) {
  const [form, setForm] = useState<TargetingPatch>(t);
  const [baseline, setBaseline] = useState<TargetingPatch>(t);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const dirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(baseline),
    [form, baseline],
  );
  const set = <K extends keyof TargetingPatch>(k: K, v: TargetingPatch[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setJustSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveTargeting(form);
      setBaseline(form);
      setJustSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      data-screen-label="targeting"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Targeting
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Your global baseline — <b>who you are and what you want</b>: role
            identity, seniority, and values. Shared across every lens; drives
            discovery and the role &amp; skill match factors.{" "}
            <b>Geography and work mode live in Search profiles</b>, not here.
          </p>
        </div>
      </header>

      <div className="mt-[24px] max-w-[760px]">
        <Field label="Role titles · synonyms (the field uses many names)">
          <TagEditor
            kind="syn"
            values={form.roleTitles}
            onChange={(v) => set("roleTitles", v)}
            suggestions={ROLE_TITLES}
          />
        </Field>
        <Field label="Seniority">
          <ChipMultiSelect
            options={SENIORITY_LEVELS}
            value={form.seniority}
            onChange={(v) => set("seniority", v)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-[24px]">
          <Field label="Must-haves">
            <TagEditor values={form.mustHaves} onChange={(v) => set("mustHaves", v)} />
          </Field>
          <Field label="Avoid">
            <TagEditor kind="avoid" values={form.avoid} onChange={(v) => set("avoid", v)} />
          </Field>
        </div>
        <Field label="Free-text preferences · fed to the model as soft signal">
          <textarea
            rows={4}
            value={form.preferences}
            onChange={(e) => set("preferences", e.target.value)}
            className="min-h-[78px] w-full resize-y rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] leading-[1.55] text-ink focus:border-ink focus:outline-none"
          />
        </Field>

        <div className="mb-[20px] flex items-center gap-[12px]">
          <Button variant="pri" onClick={handleSave} disabled={saving || !dirty}>
            {saving ? "Saving…" : "Save targeting"}
          </Button>
          {dirty && (
            <span className="font-mono text-[11.5px] text-warn">Unsaved changes</span>
          )}
          {!dirty && justSaved && (
            <span className="text-[12.5px] text-ink-2">Saved.</span>
          )}
        </div>

        <div className="flex items-center gap-[12px] rounded-[11px] border border-accent bg-accent-bg px-[18px] py-[13px] text-[13px] text-accent-ink">
          ⓘ{" "}
          <span>
            No geography here, by design — location, work mode and HQ-origin
            rules belong to <b>Search profiles</b> (lenses), so one identity can
            be viewed through many regional searches. Salary is likewise never a
            rule or signal; it&apos;s shown only when an ad states it.
          </span>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Run the TargetingView tests to verify they pass**

Run: `cd apps/web && pnpm vitest run src/components/targeting/targeting-view.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 8: Typecheck web + shared-types (catch any other `Targeting` consumer)**

Run: `cd apps/web && pnpm typecheck && cd ../../packages/shared-types && pnpm typecheck`
Expected: both exit 0. (If `seed/data.ts` or `test-fixtures.ts` errors, a seniority literal is not a valid `Seniority` — fix the literal, do not loosen the type.)

- [ ] **Step 9: Commit**

```bash
git add packages/shared-types/src/index.ts apps/web/src/lib/api/targeting.ts \
  apps/web/src/app/api/targeting/route.ts \
  apps/web/src/components/targeting/targeting-view.tsx \
  apps/web/src/components/targeting/targeting-view.test.tsx
git commit -m "feat(targeting): persistence + dirty-state save, seniority multi-select, controlled preferences, role-title suggestions"
```

---

### Task 5: Full-suite verification + live persistence browser smoke

**Files:** none (verification only).

- [ ] **Step 1: Full typecheck + lint**

Run: `just typecheck && just lint`
Expected: mypy + tsc clean; ruff + eslint clean.

- [ ] **Step 2: Full test suite**

Run: `just up && just test`
Expected: `apps/api` pytest all pass (unchanged backend); `apps/web` vitest all pass.

- [ ] **Step 3: Migrate + seed a clean DB (for the live smoke)**

Run: `just migrate && just seed`
Expected: both exit 0.

- [ ] **Step 4: Live persistence browser smoke**

This verifies the **new** behavior end-to-end (edit → save → reload → persisted) in the real app — the class of thing unit tests can't catch. Next 16 forbids a second dev server in the same dist dir, so run a dedicated no-auth instance on a separate dist dir (coexists with any running `dev-web`):

1. Ensure the API is running (`just dev-api` in another shell, or reuse an existing one on `:8000`).
2. Start the smoke web instance (background):
   `cd apps/web && PORT=3001 DEV_AUTH_BYPASS=1 NEXT_DIST_DIR=.next-authed pnpm dev`
3. Drive it with Playwright (place the script under `apps/web/` so `@playwright/test` resolves; delete it after). The script must:
   - `goto http://localhost:3001/targeting` → assert HTTP 200 and the "Targeting" heading is visible.
   - Toggle a seniority level that is NOT currently selected (e.g. `Principal`), and add a role title via the first `+ add` input (e.g. `LLM Engineer`).
   - Assert "Save targeting" is now enabled; click it; wait for "Saved.".
   - `page.reload()` → assert the `Principal` seniority chip is now `aria-pressed="true"` and the `LLM Engineer` chip is present — i.e. **the edit persisted** across reload.
4. Stop the `:3001` instance (`kill` the listener on port 3001); confirm any running `:3000` server is untouched.
5. `just seed` again to restore the demo targeting row to its seeded values.

Expected: all Playwright assertions pass (page renders, save persists across reload).

- [ ] **Step 5: Final commit (if lint/format applied any fixes)**

```bash
git add -A
git commit -m "chore(targeting): lint/format + verification pass"
```

---

## Self-Review

**Spec coverage** (each spec section → task):
- Persistence + dirty-state save → Task 4 (`saveTargeting`, BFF `PUT`, save UX). Editable seniority multi-select → Tasks 1, 2, 4. Controlled preferences → Task 4. Role-title suggestions → Tasks 1, 4 (reusing `TagEditor` `suggestions`). `ChipMultiSelect` generalization + `ModeSelect` delegation → Tasks 2, 3. `Targeting.seniority` → `Seniority[]` with read-sanitization → Tasks 1, 4. No backend change / seniority frontend-only → honored (no `apps/api` files touched). Live persistence verification → Task 5.

**Placeholder scan:** none — every step has real code or a real command with expected output. (Task 5 Step 4 describes the Playwright script's required assertions in full rather than pasting a specific throwaway file, since it's a manual verification harness, not shipped code.)

**Type consistency:** `TargetingPatch = Targeting` is the exact shape of `form` and `saveTargeting`'s argument. `ChipMultiSelect<T extends string>` is consumed as `<ChipMultiSelect<Mode>>` (ModeSelect) and `<ChipMultiSelect options={SENIORITY_LEVELS} …>` (T inferred `Seniority`); `form.seniority` is `Seniority[]`, matching. `getTargeting` narrows `string[]` → `Seniority[]` via the `SENIORITY_LEVELS` guard. The `+ add` count stays 3 (role titles + must-haves + avoid) — the seniority field is now `ChipMultiSelect`, not a `TagEditor`.
