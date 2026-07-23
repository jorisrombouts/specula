# Search-profiles (lenses) Page Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/profiles` into a full lens manager — create / edit / delete / toggle-active, all persisted — with inline-expand card editing and structured fields (scope type + predefined region/country lists, modes multi-select, origin picker, editable seeds).

**Architecture:** The backend lens CRUD (`GET`/`POST`/`PATCH`/`DELETE /lenses`) already exists; this is mostly frontend completion plus two small backend additions (a `domestic_hq` scoring branch and `isDefault` in the lens summary). Structured scope is a frontend input serialized to the existing `scope text` column (no pipeline change). Reuses `ChipMultiSelect`, `TagEditor`, `Toggle`.

**Tech Stack:** FastAPI · pytest (`apps/api`); Next 16 · React 19 · TypeScript strict · Tailwind · Vitest + Testing Library (`apps/web`); shared TS types in `packages/shared-types`.

## Global Constraints

- **Backend CRUD is done and unchanged** except two small additions (Task 1). `count`/`isNew` are **server-derived, never stored/client-set**.
- **Scope stays a `text` column.** The frontend serializes structured input to the format the existing parser reads (`""`=any, 2-letter=country, `"City, CC"`=city, else soft) and parses it back — **region catalog checked FIRST** so a 2-letter region ("EU") isn't read as a country. **`Region` is soft** (no hard filter today) — labeled as such. No pipeline change.
- **Origin mapping** (label ↔ `origin_rule` value): `Any HQ`→`""`, `Only foreign HQ`→`"foreign_hq"`, `Only domestic HQ`→`"domestic_hq"`. Unknown → `Any HQ` (lenient).
- The **default lens** (`isDefault`) is filtered out of the editable list and can't be deleted (backend 409s).
- Constraints are **frontend-only** (pickers); backend stays permissive `text`/`text[]`; reads never 500 on legacy values.
- **Run commands:** `just typecheck` (mypy + tsc), `just test` (pytest + vitest), `just lint`, `just up`, `just migrate`, `just seed`. Single web test: `cd apps/web && pnpm vitest run <path>`. Single api test: `cd apps/api && uv run pytest tests/<file>::<test> -v`. DB tests need `just up`.
- **Next 16 is not the Next you know** (`apps/web/AGENTS.md`).

---

### Task 1: Backend — `domestic_hq` scoring + `isDefault` in the lens summary

**Files:**
- Modify: `apps/api/specula_api/services/jobs.py` (`derive_loc`)
- Modify: `apps/api/specula_api/schemas/lens.py` (`LensSummaryOut`)
- Modify: `apps/api/specula_api/routers/lenses.py` (`_summary`)
- Modify: `apps/api/tests/test_jobs_scoring.py`, `apps/api/tests/test_lenses_api.py`

**Interfaces:**
- Produces: `origin_rule == "domestic_hq"` scored symmetric to `foreign_hq`; `LensSummaryOut.is_default: bool` (camelCased `isDefault`).

- [ ] **Step 1: Start DB**

Run: `just up`
Expected: Postgres container up.

- [ ] **Step 2: Write the failing tests**

In `apps/api/tests/test_jobs_scoring.py`, add to `class TestDeriveLoc` (right after `test_foreign_hq_lens_rewards_non_local_hq`):

```python
    def test_domestic_hq_lens_rewards_local_hq(self) -> None:
        local = derive_loc("Remote", "NL", "NL", is_default=False, origin_rule="domestic_hq")
        foreign = derive_loc("Remote", "NL", "GB", is_default=False, origin_rule="domestic_hq")
        assert local > foreign
```

In `apps/api/tests/test_lenses_api.py`, add (uses the existing helpers; the GET lazily creates the default lens):

```python
@requires_db
async def test_summary_exposes_is_default(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rows = (await client.get("/api/v1/lenses", headers=_auth_header())).json()
    assert any(r["isDefault"] for r in rows)
    assert all("isDefault" in r for r in rows)
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_jobs_scoring.py::TestDeriveLoc::test_domestic_hq_lens_rewards_local_hq tests/test_lenses_api.py::test_summary_exposes_is_default -v`
Expected: FAIL — `domestic_hq` isn't scored (local == foreign); `isDefault` missing from the summary (KeyError).

- [ ] **Step 4: Add the `domestic_hq` branch**

In `apps/api/specula_api/services/jobs.py`, in `derive_loc`, replace:

```python
    factor = base
    if origin_rule == "foreign_hq":
        factor += 8 if (hq and country and hq != country) else -8
    return _clamp(factor)
```

with:

```python
    factor = base
    if origin_rule == "foreign_hq":
        factor += 8 if (hq and country and hq != country) else -8
    elif origin_rule == "domestic_hq":
        factor += 8 if (hq and country and hq == country) else -8
    return _clamp(factor)
```

- [ ] **Step 5: Add `is_default` to the summary**

In `apps/api/specula_api/schemas/lens.py`, add to `LensSummaryOut` (after `is_new: int`):

```python
    is_default: bool
```

In `apps/api/specula_api/routers/lenses.py`, in `_summary`, add `is_default=lens.is_default,` to the `LensSummaryOut(...)` constructor (e.g. right after `is_new=is_new,`).

- [ ] **Step 6: Run to verify GREEN + mypy**

Run: `cd apps/api && uv run pytest tests/test_jobs_scoring.py tests/test_lenses_api.py -v && uv run mypy .`
Expected: PASS; mypy clean.

- [ ] **Step 7: Commit**

```bash
git add apps/api/specula_api/services/jobs.py apps/api/specula_api/schemas/lens.py apps/api/specula_api/routers/lenses.py apps/api/tests/test_jobs_scoring.py apps/api/tests/test_lenses_api.py
git commit -m "feat(lenses): domestic_hq scoring branch + isDefault in lens summary"
```

---

### Task 2: Frontend — lens catalog + scope/origin helpers

**Files:**
- Create: `apps/web/src/lib/lens-catalog.ts`
- Test: `apps/web/src/lib/lens-catalog.test.ts`

**Interfaces:**
- Produces: `SCOPE_TYPES`, `ScopeType`, `REGIONS`, `COUNTRIES`, `ORIGIN_OPTIONS`, `originLabel(value)`, `parseScope(text): {type,value}`, `serializeScope({type,value}): string`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/lens-catalog.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { parseScope, serializeScope, originLabel } from "@/lib/lens-catalog";

describe("lens-catalog scope helpers", () => {
  it("parseScope classifies each scope form (region before country)", () => {
    expect(parseScope("")).toEqual({ type: "Any", value: "" });
    expect(parseScope("EU")).toEqual({ type: "Region", value: "EU" }); // region, not country
    expect(parseScope("ES")).toEqual({ type: "Country", value: "ES" });
    expect(parseScope("Berlin, DE")).toEqual({ type: "City", value: "Berlin, DE" });
  });
  it("serializeScope is the inverse (Any -> empty)", () => {
    expect(serializeScope({ type: "Any", value: "" })).toBe("");
    expect(serializeScope({ type: "Country", value: "ES" })).toBe("ES");
    expect(serializeScope(parseScope("EU"))).toBe("EU");
  });
  it("originLabel maps values, unknown -> Any HQ", () => {
    expect(originLabel("foreign_hq")).toBe("Only foreign HQ");
    expect(originLabel("domestic_hq")).toBe("Only domestic HQ");
    expect(originLabel("")).toBe("Any HQ");
    expect(originLabel("whatever")).toBe("Any HQ");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/lib/lens-catalog.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the catalog**

Create `apps/web/src/lib/lens-catalog.ts`:

```ts
export const SCOPE_TYPES = ["Any", "Region", "Country", "City"] as const;
export type ScopeType = (typeof SCOPE_TYPES)[number];

// Curated frontend catalogs (data-quality pickers; backend does not validate).
export const REGIONS: string[] = [
  "EU", "EEA", "Eurozone", "Nordics", "DACH", "Benelux", "UK & Ireland",
  "Southern Europe", "North America", "LATAM", "Global",
];
export const COUNTRIES: [string, string][] = [
  ["NL", "Netherlands"], ["DE", "Germany"], ["FR", "France"], ["ES", "Spain"],
  ["IT", "Italy"], ["PT", "Portugal"], ["BE", "Belgium"], ["IE", "Ireland"],
  ["DK", "Denmark"], ["SE", "Sweden"], ["NO", "Norway"], ["FI", "Finland"],
  ["PL", "Poland"], ["AT", "Austria"], ["CH", "Switzerland"], ["CZ", "Czechia"],
  ["GB", "United Kingdom"], ["US", "United States"], ["CA", "Canada"],
];

export const ORIGIN_OPTIONS: { label: string; value: string }[] = [
  { label: "Any HQ", value: "" },
  { label: "Only foreign HQ", value: "foreign_hq" },
  { label: "Only domestic HQ", value: "domestic_hq" },
];
export const originLabel = (value: string): string =>
  ORIGIN_OPTIONS.find((o) => o.value === value)?.label ?? "Any HQ";

export type ScopeParts = { type: ScopeType; value: string };

// scope text (stored) -> structured. Region catalog is checked FIRST so a 2-letter
// region ("EU") isn't mistaken for a country code.
export function parseScope(text: string): ScopeParts {
  const t = (text ?? "").trim();
  if (t === "") return { type: "Any", value: "" };
  if (REGIONS.includes(t)) return { type: "Region", value: t };
  if (/^[A-Z]{2}$/.test(t)) return { type: "Country", value: t };
  return { type: "City", value: t };
}
export function serializeScope({ type, value }: ScopeParts): string {
  return type === "Any" ? "" : value.trim();
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/lib/lens-catalog.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/lens-catalog.ts apps/web/src/lib/lens-catalog.test.ts
git commit -m "feat(lenses): scope/origin catalog + parse/serialize helpers"
```

---

### Task 3: Frontend — `isDefault` type, lens CRUD client + BFF routes

Additive plumbing — ends green via typecheck + the existing (unchanged) profiles test.

**Files:**
- Modify: `packages/shared-types/src/index.ts` (`LensSummary` += `isDefault`)
- Modify: `apps/web/src/lib/seed/logic.ts` (`deriveLensSummaries` sets `isDefault`)
- Modify: `apps/web/src/lib/api/lenses.ts` (client CRUD)
- Modify: `apps/web/src/app/api/lenses/route.ts` (add `POST`)
- Create: `apps/web/src/app/api/lenses/[id]/route.ts` (`PATCH`, `DELETE`)

**Interfaces:**
- Produces: `LensSummary.isDefault: boolean`; `LensPatch`, `createLens`, `updateLens`, `deleteLens`.

- [ ] **Step 1: Add `isDefault` to `LensSummary`**

In `packages/shared-types/src/index.ts`, change the `LensSummary` interface to:

```ts
export interface LensSummary extends Lens { count: number; isNew: number; isDefault: boolean }
```

- [ ] **Step 2: Set `isDefault` in `deriveLensSummaries`**

In `apps/web/src/lib/seed/logic.ts`, find the `deriveLensSummaries` function that builds each `LensSummary`. In the object it returns per lens, add `isDefault: lens.id === "all",` (the seed's `"all"` lens is the default). If the function spreads the lens (`...lens`), add the field to the returned object; the return type is `LensSummary[]`, so tsc will confirm completeness.

- [ ] **Step 3: Add the client CRUD functions**

Replace the entire contents of `apps/web/src/lib/api/lenses.ts` with:

```ts
import type { LensSummary, Mode } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export async function getLenses(): Promise<LensSummary[]> {
  return bffFetch<LensSummary[]>("/lenses");
}

// The editable lens payload (camelCase; `origin` carries the origin_rule value).
export type LensPatch = {
  name: string;
  short: string;
  scope: string;
  modes: Mode[];
  origin: string;
  focus: string;
  seeds: string[];
  active: boolean;
};

export async function createLens(patch: LensPatch): Promise<LensSummary> {
  const res = await fetch("/api/lenses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Failed to create lens (${res.status})`);
  return (await res.json()) as LensSummary;
}

export async function updateLens(id: string, patch: Partial<LensPatch>): Promise<LensSummary> {
  const res = await fetch(`/api/lenses/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Failed to update lens (${res.status})`);
  return (await res.json()) as LensSummary;
}

export async function deleteLens(id: string): Promise<void> {
  const res = await fetch(`/api/lenses/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete lens (${res.status})`);
}
```

- [ ] **Step 4: Add `POST` to the lenses BFF route**

Replace the entire contents of `apps/web/src/app/api/lenses/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getLenses } from "@/lib/api/lenses";
import { bffFetch } from "@/lib/api/bff";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getLenses());
}

export async function POST(request: Request): Promise<NextResponse> {
  const body = await request.json();
  const created = await bffFetch("/lenses", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return NextResponse.json(created, { status: 201 });
}
```

- [ ] **Step 5: Create the `[id]` BFF route**

Create `apps/web/src/app/api/lenses/[id]/route.ts`:

```ts
import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const body = await request.json();
  const updated = await bffFetch(`/lenses/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return NextResponse.json(updated);
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  await bffFetch(`/lenses/${id}`, { method: "DELETE" });
  return new NextResponse(null, { status: 204 });
}
```

- [ ] **Step 6: Typecheck + existing tests**

Run: `cd apps/web && pnpm typecheck && cd ../../packages/shared-types && pnpm typecheck && cd ../../apps/web && pnpm vitest run src/components/profiles/profiles-view.test.tsx`
Expected: typecheck clean (both); the existing profiles test still passes (it doesn't use `isDefault` or the new functions yet).

- [ ] **Step 7: Commit**

```bash
git add packages/shared-types/src/index.ts apps/web/src/lib/seed/logic.ts apps/web/src/lib/api/lenses.ts apps/web/src/app/api/lenses/route.ts apps/web/src/app/api/lenses/[id]/route.ts
git commit -m "feat(lenses): isDefault type + CRUD client + BFF POST/PATCH/DELETE routes"
```

---

### Task 4: Frontend — `LensEditor` inline edit component

**Files:**
- Create: `apps/web/src/components/profiles/lens-editor.tsx`
- Test: `apps/web/src/components/profiles/lens-editor.test.tsx`

**Interfaces:**
- Consumes: `lens-catalog` (Task 2), `LensPatch` (Task 3), `ChipMultiSelect`, `TagEditor`, `Button`, `Field`, `WORK_MODES`.
- Produces: `<LensEditor lens={...} isNew? onSave={(p: LensPatch)=>void} onCancel={()=>void} onDelete={()=>void} />`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/profiles/lens-editor.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { LensEditor } from "@/components/profiles/lens-editor";

afterEach(cleanup);

const lens = {
  name: "Spain",
  scope: "ES",
  modes: ["Remote", "Hybrid"] as ("Remote" | "Hybrid" | "On-site")[],
  origin: "foreign_hq",
  focus: "Barcelona",
  seeds: ["ml engineer Barcelona"],
  active: true,
};

describe("LensEditor", () => {
  it("saves the edited fields with the scope serialized and origin value", () => {
    const onSave = vi.fn();
    render(<LensEditor lens={lens} onSave={onSave} onCancel={() => {}} onDelete={() => {}} />);
    fireEvent.change(screen.getByLabelText("profile name"), { target: { value: "Iberia" } });
    fireEvent.click(screen.getByText("Save profile"));
    expect(onSave).toHaveBeenCalledTimes(1);
    const patch = onSave.mock.calls[0][0];
    expect(patch.name).toBe("Iberia");
    expect(patch.scope).toBe("ES"); // Country -> serialized code
    expect(patch.origin).toBe("foreign_hq");
    expect(patch.short).toBe("Iberia");
  });

  it("switching scope type swaps the value control (Country select -> City text)", () => {
    render(<LensEditor lens={lens} onSave={() => {}} onCancel={() => {}} onDelete={() => {}} />);
    expect(screen.getByLabelText("scope value")).toBeInTheDocument(); // Country select
    fireEvent.change(screen.getByLabelText("scope type"), { target: { value: "City" } });
    fireEvent.change(screen.getByLabelText("scope value"), { target: { value: "Madrid, ES" } });
    // Save and confirm the City value serializes through
    const onSave = vi.fn();
    cleanup();
    render(<LensEditor lens={lens} onSave={onSave} onCancel={() => {}} onDelete={() => {}} />);
    fireEvent.change(screen.getByLabelText("scope type"), { target: { value: "City" } });
    fireEvent.change(screen.getByLabelText("scope value"), { target: { value: "Madrid, ES" } });
    fireEvent.click(screen.getByText("Save profile"));
    expect(onSave.mock.calls[0][0].scope).toBe("Madrid, ES");
  });

  it("fires onCancel and onDelete", () => {
    const onCancel = vi.fn();
    const onDelete = vi.fn();
    render(<LensEditor lens={lens} onSave={() => {}} onCancel={onCancel} onDelete={onDelete} />);
    fireEvent.click(screen.getByText("Cancel"));
    fireEvent.click(screen.getByText("Delete"));
    expect(onCancel).toHaveBeenCalled();
    expect(onDelete).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/profiles/lens-editor.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/profiles/lens-editor.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import type { Mode } from "@specula/shared-types";
import { WORK_MODES } from "@specula/shared-types";
import { ChipMultiSelect } from "@/components/atoms/chip-multi-select";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Field } from "@/components/config/field";
import { Button } from "@/components/atoms/button";
import {
  COUNTRIES,
  ORIGIN_OPTIONS,
  REGIONS,
  SCOPE_TYPES,
  parseScope,
  serializeScope,
  type ScopeParts,
  type ScopeType,
} from "@/lib/lens-catalog";
import type { LensPatch } from "@/lib/api/lenses";

const INPUT =
  "w-full rounded-[8px] border border-rule-2 bg-card px-[10px] py-[8px] font-body text-[13px] text-ink focus:border-ink focus:outline-none";

type EditableLens = {
  name: string;
  scope: string;
  modes: Mode[];
  origin: string;
  focus: string;
  seeds: string[];
  active: boolean;
};

export function LensEditor({
  lens,
  isNew = false,
  onSave,
  onCancel,
  onDelete,
}: {
  lens: EditableLens;
  isNew?: boolean;
  onSave: (patch: LensPatch) => void;
  onCancel: () => void;
  onDelete: () => void;
}) {
  const [name, setName] = useState(lens.name);
  const [scope, setScope] = useState<ScopeParts>(() => parseScope(lens.scope));
  const [modes, setModes] = useState<Mode[]>(lens.modes);
  const [origin, setOrigin] = useState(lens.origin);
  const [focus, setFocus] = useState(lens.focus);
  const [seeds, setSeeds] = useState<string[]>(lens.seeds);

  const patch = (): LensPatch => ({
    name: name.trim(),
    short: name.trim(),
    scope: serializeScope(scope),
    modes,
    origin,
    focus,
    seeds,
    active: lens.active,
  });

  const initial = useMemo(() => JSON.stringify(parseScope(lens.scope)) + lens.name, []);
  const dirty =
    JSON.stringify(scope) + name !== initial ||
    modes.join() !== lens.modes.join() ||
    origin !== lens.origin ||
    focus !== lens.focus ||
    seeds.join() !== lens.seeds.join();
  const canSave = name.trim() !== "" && (isNew || dirty);

  const setScopeType = (type: ScopeType) => {
    let value = scope.value;
    if (type === "Any") value = "";
    else if (type === "Region" && !REGIONS.includes(value)) value = REGIONS[0];
    else if (type === "Country" && !COUNTRIES.some(([c]) => c === value)) value = COUNTRIES[0][0];
    else if (type === "City" && (REGIONS.includes(value) || /^[A-Z]{2}$/.test(value))) value = "";
    setScope({ type, value });
  };

  return (
    <div
      data-lens-edit
      className="rounded-[14px] border border-accent bg-card p-[18px_22px] shadow-card"
    >
      <div className="mb-[14px] flex items-center gap-[14px]">
        <input
          aria-label="profile name"
          className="min-w-[220px] rounded-[8px] border border-rule-2 bg-card px-[11px] py-[7px] font-display text-[18px] font-semibold text-ink focus:border-ink focus:outline-none"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Profile name"
        />
      </div>

      <div className="grid grid-cols-3 gap-[16px]">
        <Field label="Location scope · hard">
          <div className="flex gap-2">
            <select
              aria-label="scope type"
              className={`${INPUT} w-[104px] flex-none`}
              value={scope.type}
              onChange={(e) => setScopeType(e.target.value as ScopeType)}
            >
              {SCOPE_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            {scope.type === "Any" ? (
              <span className="self-center pl-1 text-[12px] text-ink-2">no location filter</span>
            ) : scope.type === "Region" ? (
              <select
                aria-label="scope value"
                className={`${INPUT} flex-1`}
                value={scope.value}
                onChange={(e) => setScope({ type: "Region", value: e.target.value })}
              >
                {REGIONS.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            ) : scope.type === "Country" ? (
              <select
                aria-label="scope value"
                className={`${INPUT} flex-1`}
                value={scope.value}
                onChange={(e) => setScope({ type: "Country", value: e.target.value })}
              >
                {COUNTRIES.map(([c, n]) => (
                  <option key={c} value={c}>
                    {n} ({c})
                  </option>
                ))}
              </select>
            ) : (
              <input
                aria-label="scope value"
                className={`${INPUT} flex-1`}
                placeholder="City, CC — e.g. Berlin, DE"
                value={scope.value}
                onChange={(e) => setScope({ type: "City", value: e.target.value })}
              />
            )}
          </div>
        </Field>
        <Field label="Work mode · hard">
          <ChipMultiSelect options={WORK_MODES} value={modes} onChange={setModes} />
        </Field>
        <Field label="Origin rule · hard">
          <select
            aria-label="origin rule"
            className={INPUT}
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          >
            {ORIGIN_OPTIONS.map((o) => (
              <option key={o.label} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div className="mt-[8px] grid grid-cols-2 gap-[16px]">
        <Field label="Focus · soft signal">
          <input
            aria-label="focus"
            className={INPUT}
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="soft preference, e.g. async-first teams"
          />
        </Field>
        <Field label="Discovery seeds · editable">
          <TagEditor values={seeds} onChange={setSeeds} />
        </Field>
      </div>

      <div className="mt-[16px] flex items-center gap-[10px] border-t border-rule pt-[15px]">
        <Button variant="pri" disabled={!canSave} onClick={() => onSave(patch())}>
          Save profile
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
        {dirty && (
          <span className="font-mono text-[11px] text-warn">Unsaved changes</span>
        )}
        <button
          type="button"
          onClick={onDelete}
          className="ml-auto rounded-[8px] border border-transparent px-[13px] py-2 text-[12.5px] text-warn hover:bg-warn-bg"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/profiles/lens-editor.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/profiles/lens-editor.tsx apps/web/src/components/profiles/lens-editor.test.tsx
git commit -m "feat(lenses): LensEditor inline edit form"
```

---

### Task 5: Frontend — `ProfilesView` rewrite + integration

**Files:**
- Modify: `apps/web/src/components/profiles/profiles-view.tsx` (rewrite)
- Modify: `apps/web/src/components/profiles/profiles-view.test.tsx`
- Modify: `apps/web/src/lib/seed/data.ts` (normalize lens `origin` to `origin_rule` values)

**Interfaces:**
- Consumes: `LensEditor` (Task 4), `lens-catalog` (Task 2), lens CRUD client (Task 3), `Toggle`, `Button`.

- [ ] **Step 1: Normalize seed lens `origin` values**

In `apps/web/src/lib/seed/data.ts`, in the `lenses` array, change each lens's `origin` from the display label to the `origin_rule` value so the seed matches the API contract:
- `"Any HQ"` → `""`
- `"Only foreign HQ"` → `"foreign_hq"`

(Result: `all`/`remote`/`spain`/`berlin` → `origin: ""`; `foreign` → `origin: "foreign_hq"`.)

- [ ] **Step 2: Update the ProfilesView tests**

Replace the entire contents of `apps/web/src/components/profiles/profiles-view.test.tsx` with:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, fireEvent, cleanup, within, screen } from "@testing-library/react";
import { ProfilesView } from "@/components/profiles/profiles-view";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getLenses } = await import("@/lib/api/lenses");

afterEach(cleanup);
const lenses = await getLenses();

function mockFetchOk(body: unknown = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
}

describe("ProfilesView", () => {
  it("shows DERIVED active/total (4 active / 5 total) and 4 cards (excludes the default)", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("4");
    expect(header).toHaveTextContent("active");
    expect(header).toHaveTextContent("5");
    expect(header).toHaveTextContent("total");
    expect(container.querySelectorAll("[data-lens]")).toHaveLength(4);
    expect(container.querySelector('[data-lens="all"]')).toBeNull();
  });

  it("renders a lens card's DERIVED count badge + scope", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const remote = lenses.find((l) => l.id === "remote")!;
    const card = container.querySelector('[data-lens="remote"]') as HTMLElement;
    expect(
      within(card).getByText(`${remote.count} roles · ${remote.isNew} new`),
    ).toBeInTheDocument();
    expect(card).toHaveTextContent("EU"); // scope "EU" shown as "Region · EU"
  });

  it("+ New profile adds an editable card", () => {
    render(<ProfilesView lenses={lenses} />);
    expect(screen.queryByText("Save profile")).toBeNull();
    fireEvent.click(screen.getByText("+ New profile"));
    expect(screen.getByText("Save profile")).toBeInTheDocument();
  });

  it("toggling a lens flips it and PATCHes active", async () => {
    const fetchMock = mockFetchOk({});
    const { container } = render(<ProfilesView lenses={lenses} />);
    const berlin = container.querySelector('[data-lens="berlin"]') as HTMLElement;
    expect(berlin.getAttribute("data-active")).toBe("false");
    fireEvent.click(within(berlin).getByRole("switch"));
    expect(
      container.querySelector('[data-lens="berlin"]')!.getAttribute("data-active"),
    ).toBe("true"); // optimistic
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/lenses/berlin"),
      expect.objectContaining({ method: "PATCH" }),
    );
    fetchMock.mockRestore();
  });

  it("editing a card and saving PATCHes with the mapped payload", async () => {
    const fetchMock = mockFetchOk(lenses.find((l) => l.id === "spain"));
    const { container } = render(<ProfilesView lenses={lenses} />);
    const spain = container.querySelector('[data-lens="spain"]') as HTMLElement;
    fireEvent.click(within(spain).getByText("Edit"));
    fireEvent.change(screen.getByLabelText("focus"), { target: { value: "Madrid only" } });
    fireEvent.click(screen.getByText("Save profile"));
    await screen.findByText("Edit"); // back to read-only after save
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/lenses/spain"),
      expect.objectContaining({ method: "PATCH" }),
    );
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
    expect(body.focus).toBe("Madrid only");
    expect(body.scope).toBe("ES");
    fetchMock.mockRestore();
  });
});
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd apps/web && pnpm vitest run src/components/profiles/profiles-view.test.tsx`
Expected: FAIL — the current view has no Edit affordance, no "Save profile", and doesn't PATCH.

- [ ] **Step 4: Rewrite `profiles-view.tsx`**

Replace the entire contents of `apps/web/src/components/profiles/profiles-view.tsx` with:

```tsx
"use client";

import { useState } from "react";
import type { LensSummary } from "@specula/shared-types";
import { Toggle } from "@/components/atoms/toggle";
import { Button } from "@/components/atoms/button";
import { LensEditor } from "@/components/profiles/lens-editor";
import { originLabel, parseScope } from "@/lib/lens-catalog";
import {
  createLens,
  deleteLens,
  updateLens,
  type LensPatch,
} from "@/lib/api/lenses";

const scopeLabel = (scope: string): string => {
  const p = parseScope(scope);
  return p.type === "Any" ? "Any region" : `${p.type} · ${p.value}`;
};

function Rule({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <div className="mb-[6px] font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">
        {label}
      </div>
      <div className={`text-[13px] ${muted ? "text-ink-2" : "text-ink"}`}>{value}</div>
    </div>
  );
}

type Row = { lens: LensSummary; editing: boolean; isNew: boolean; key: string };
let tmp = 0;

export function ProfilesView({ lenses: seed }: { lenses: LensSummary[] }) {
  const defaults = seed.filter((l) => l.isDefault);
  const [rows, setRows] = useState<Row[]>(() =>
    seed
      .filter((l) => !l.isDefault)
      .map((l) => ({ lens: l, editing: false, isNew: false, key: l.id })),
  );

  const activeN = defaults.filter((l) => l.active).length + rows.filter((r) => r.lens.active).length;
  const totalN = defaults.length + rows.length;

  const setRow = (key: string, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const addNew = () => {
    const key = `new-${tmp++}`;
    const blank: LensSummary = {
      id: key, name: "", short: "", active: true, scope: "", modes: ["Remote"],
      origin: "", focus: "", seeds: [], count: 0, isNew: 0, isDefault: false,
    };
    setRows((rs) => [...rs, { lens: blank, editing: true, isNew: true, key }]);
  };

  const cancel = (row: Row) =>
    row.isNew ? setRows((rs) => rs.filter((r) => r.key !== row.key)) : setRow(row.key, { editing: false });

  const save = async (row: Row, patch: LensPatch) => {
    if (row.isNew) {
      const created = await createLens(patch);
      setRows((rs) =>
        rs.map((r) => (r.key === row.key ? { lens: created, editing: false, isNew: false, key: created.id } : r)),
      );
    } else {
      const updated = await updateLens(row.lens.id, patch);
      setRow(row.key, { lens: updated, editing: false });
    }
  };

  const remove = async (row: Row) => {
    if (!row.isNew) await deleteLens(row.lens.id);
    setRows((rs) => rs.filter((r) => r.key !== row.key));
  };

  const toggle = async (row: Row) => {
    const active = !row.lens.active;
    setRow(row.key, { lens: { ...row.lens, active } });
    await updateLens(row.lens.id, { active });
  };

  return (
    <section
      data-screen-label="profiles"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Search profiles
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Named lenses over one shared pool. Each{" "}
            <b>owns geography &amp; work mode entirely</b> — location scope,
            allowed modes, and HQ-origin rule — layered over your global
            targeting baseline. A role can match several at once; switching a
            lens re-scopes the Jobs view.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">{activeN}</b> active
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{totalN}</b> total
          </div>
        </div>
      </header>

      <div className="mt-[22px] flex flex-col gap-[13px]">
        {rows.map((row) =>
          row.editing ? (
            <LensEditor
              key={row.key}
              lens={row.lens}
              isNew={row.isNew}
              onSave={(p) => save(row, p)}
              onCancel={() => cancel(row)}
              onDelete={() => remove(row)}
            />
          ) : (
            <div
              key={row.key}
              data-lens={row.lens.id}
              data-active={row.lens.active}
              className={`rounded-[14px] border border-rule bg-card p-[18px_22px] shadow-card transition-colors hover:border-rule-2 ${row.lens.active ? "" : "opacity-60"}`}
            >
              <div className="mb-[14px] flex items-center gap-[14px]">
                <span className="font-display text-[19px] font-semibold">{row.lens.name}</span>
                <span className="font-mono text-[10px] text-ink-2">
                  {row.lens.count} roles · {row.lens.isNew} new
                </span>
                <span className="ml-auto flex items-center gap-[14px]">
                  <button
                    type="button"
                    onClick={() => setRow(row.key, { editing: true })}
                    className="cursor-pointer border-none bg-transparent font-mono text-[10.5px] uppercase tracking-[0.06em] text-ink-2 hover:text-ink"
                  >
                    Edit
                  </button>
                  <Toggle on={row.lens.active} onChange={() => toggle(row)} />
                </span>
              </div>
              <div className="grid grid-cols-3 gap-[16px]">
                <Rule label="Location scope · hard" value={scopeLabel(row.lens.scope)} />
                <Rule label="Work mode · hard" value={row.lens.modes.join(" / ") || "—"} />
                <Rule label="Origin rule · hard" value={originLabel(row.lens.origin)} />
              </div>
              <div className="mt-[16px] grid grid-cols-2 gap-[16px]">
                <Rule label="Focus · soft signal" value={row.lens.focus || "—"} muted />
                <div>
                  <div className="mb-[6px] font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">
                    Discovery seeds
                  </div>
                  <div className="mt-[6px] flex flex-wrap gap-[6px]">
                    {row.lens.seeds.map((s) => (
                      <span
                        key={s}
                        className="rounded-[5px] bg-panel px-[8px] py-[3px] font-mono text-[10.5px] text-ink-2"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ),
        )}
      </div>
      <Button className="mt-[16px]" onClick={addNew}>
        + New profile
      </Button>
    </section>
  );
}
```

- [ ] **Step 5: Run the ProfilesView tests to verify they pass**

Run: `cd apps/web && pnpm vitest run src/components/profiles/profiles-view.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 6: Typecheck + full web suite**

Run: `cd apps/web && pnpm typecheck && pnpm test`
Expected: tsc clean; all vitest pass (catches any other `LensSummary`/seed consumer).

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/profiles/profiles-view.tsx apps/web/src/components/profiles/profiles-view.test.tsx apps/web/src/lib/seed/data.ts
git commit -m "feat(lenses): ProfilesView CRUD — inline-expand editing, create/edit/delete/toggle"
```

---

### Task 6: Full-suite verification + live browser smoke

**Files:** none (verification only).

- [ ] **Step 1: Full typecheck + lint**

Run: `just typecheck && just lint`
Expected: mypy + tsc clean; ruff + eslint clean.

- [ ] **Step 2: Full test suite**

Run: `just up && just test`
Expected: `apps/api` pytest all pass (incl. domestic_hq + isDefault); `apps/web` vitest all pass.

- [ ] **Step 3: Migrate + seed**

Run: `just migrate && just seed`
Expected: both exit 0.

- [ ] **Step 4: Live CRUD browser smoke**

Verify create → persist end-to-end in the real app. Next 16 forbids a second dev server in the same dist dir, so use a separate dist dir (coexists with any running `dev-web`):

1. Ensure the API runs on `:8000` (`just dev-api`), DB seeded.
2. Start the smoke instance (background):
   `cd apps/web && PORT=3001 DEV_AUTH_BYPASS=1 NEXT_DIST_DIR=.next-authed pnpm dev`
3. Drive with Playwright (script under `apps/web/`, delete after). It must:
   - `goto http://localhost:3001/profiles` → assert HTTP 200 and the "Search profiles" heading.
   - Click **"+ New profile"** → a `LensEditor` appears; set the name (e.g. `Amsterdam core`), set Scope type = City with value `Amsterdam, NL`, toggle a work mode, add a seed via the seeds `TagEditor` (type + Enter), click **Save profile**; the card returns to read-only showing the name.
   - `page.reload()` → assert the new `Amsterdam core` card is present (**persisted**), and the header total incremented.
   - Edit that card (change Focus) → Save → reload → the change persists.
   - Delete that card → reload → it's gone.
4. Stop `:3001` (`kill` the listener); confirm any `:3000` server is untouched.
5. `just seed` again to restore the demo lenses.

Expected: all Playwright assertions pass (create/edit/delete persist across reload).

- [ ] **Step 5: Final commit (if lint/format applied fixes)**

```bash
git add -A
git commit -m "chore(lenses): lint/format + verification pass"
```

---

## Self-Review

**Spec coverage:**
- Full CRUD + inline-expand editing → Tasks 3–5. Structured scope (type + predefined region/country, serialized to text) → Tasks 2, 4. Modes multi-select → Task 4 (`ChipMultiSelect`). Origin picker (Any/foreign/domestic, mapped) → Tasks 2, 4. Editable seeds → Task 4 (`TagEditor`). Toggle-active persistence + counts derived → Task 5. `domestic_hq` scoring + `isDefault` (filter/protect default) → Task 1, 3, 5. Region-first scope parse → Task 2. Live persistence verification → Task 6.
- No pipeline/scope-WHERE change; no auto-seed generation; frontend-only constraints — honored.

**Placeholder scan:** none — real code or a real command with expected output per step. (Task 6 Step 4 fully specifies the Playwright assertions rather than pasting a throwaway file.)

**Type consistency:** `LensPatch` is the shape produced by `LensEditor` and consumed by `createLens`/`updateLens`; `serializeScope`/`parseScope` round-trip (region-first); `originLabel`/`ORIGIN_OPTIONS` map value↔label consistently; `LensSummary.isDefault` is set by `deriveLensSummaries` (seed) and the backend `_summary` (live), and `ProfilesView` filters on it. The read-only card renders `scopeLabel(scope)` and `originLabel(origin)` from the same helpers the editor serializes into.
