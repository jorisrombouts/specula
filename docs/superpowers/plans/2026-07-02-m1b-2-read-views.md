# M1b-2 — Read views (Approvals · Companies · Insights) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the prototype's three read views — Approval queue, Companies registry, Insights dashboard — to typed React against the M1a seed/atoms, statically (pixel-faithful, real derived data), with only the Companies text-filter live; all persisting actions inert (M2) and all animations deferred (M1c).

**Architecture:** Follows the M1b-1 pattern exactly: a typed `lib/api/` data-access layer wraps the seed and the three remaining `/api` routes call it (DRY). Each RSC page fetches its data and passes it to a view component. Approvals + Insights have no interactivity → they are **server components** (no client boundary). Only `CompaniesView` is `"use client"` (it holds the ephemeral filter string, like M1b-1's lens/sort).

**Tech Stack:** Next.js 16 (App Router, RSC + client islands), React 19, TypeScript strict, Tailwind v4 (CSS-first, arbitrary values translating `views.css`), Vitest + @testing-library/react (jsdom), `@specula/shared-types`.

## Global Constraints

- **Next.js 16, TypeScript strict, Tailwind-native.** Rebuild each prototype component in Tailwind arbitrary-value classes translated from `prototype/specula/views.css` + `specula.css`. Do **not** import prototype CSS. Match the M1b-1 idiom + theme tokens in `apps/web/src/app/globals.css` (`paper`, `panel`, `panel-2`, `card`, `ink`, `ink-2`, `ink-3`, `rule`, `rule-2`, `accent`, `accent-bg`, `accent-ink`, `warn`, `warn-bg`, `gold`; `font-display`/`font-body`/`font-mono`; `shadow-card`/`shadow-pop`). Prototype `var(--rule-2)` → Tailwind `rule-2`, etc. CSS-var color strings from the seed (`"var(--accent)"`, `"#9A7A18"`) are applied via inline `style`.
- **Counts DERIVED, never hard-coded.** Companies `{companies.length} tracked` + `{Σ open} open roles` (reduce); Approvals `{approvals.length} pending`; the filter's "N of M". Never cosmetic constants.
- **Salary / comp display-only.** The Companies comp-est chip + the Insights salary panel are informational; never sort/filter/score. Keep the salary panel's "Never used to rank or filter" caption.
- **Low-confidence "surfaced, not trusted".** Insights renders the "⚐ N low-confidence extractions excluded… treat trends as directional" banner; Companies flags HQ-confidence `< 80` with warn styling + `⚐`.
- **Animations → M1c.** Render every bar/segment/number at its FINAL value. No `run`-gated grow, no `useCountUp`, no card exit. Structure widths from a computed value (not a magic literal) so M1c can gate them.
- **Persisting actions → M2 (inert).** Approvals Approve/Reject/Snooze buttons, the Companies tracking Toggle, and the Insights period `<select>` render at full fidelity but do nothing (no handlers / no-op). Consequence: the Approvals header shows `0 approved` (no live log). Same rule as M1b-1's drawer controls.
- **Testing = Vitest component + data-access tests** (`import { describe, it, expect, afterEach } from "vitest"`; `render/screen/fireEvent/cleanup` from `@testing-library/react`; `afterEach(cleanup)`). Views are auth-gated → **no new E2E**.
- **Sources of truth:** `pipeline.jsx` (Approvals+Companies), `intel.jsx` (Insights), `views.css`/`specula.css` (styling), spec `docs/superpowers/specs/2026-07-02-m1b-2-read-views-design.md`. All commands run from `apps/web`.
- **Seed facts (fixed by the M1a seed):** 6 approvals (a5 = Sereact `unverified`); 10 companies, `Σ open = 67`, only Sereact `conf 64 (<80)`; insights `totalAnalysed 312`, `lowConfExcluded 24`, 7 skillDemand rows (Kubernetes + Go have `gap: true`), trend 8 weeks × 3 series, 5 seniority, 3 mode, 4 salary bands, 5 active companies (Mistral top).

---

### Task 1: Data-access layer + `/api` route refactor (DRY)

**Files:**
- Create: `apps/web/src/lib/api/approvals.ts`, `apps/web/src/lib/api/companies.ts`, `apps/web/src/lib/api/insights.ts`
- Test: `apps/web/src/lib/api/read-views.test.ts`
- Modify: `apps/web/src/app/api/approvals/route.ts`, `apps/web/src/app/api/companies/route.ts`, `apps/web/src/app/api/insights/route.ts`

**Interfaces:**
- Consumes: `approvals`, `companies`, `insights` from `@/lib/seed/data`; types from `@specula/shared-types`.
- Produces (later tasks + RSC pages rely on these):
  - `getApprovals(): Approval[]`
  - `getCompanies(): Company[]`
  - `getInsights(): Insights`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/api/read-views.test.ts`:

```tsx
import { describe, it, expect } from "vitest";
import { getApprovals } from "@/lib/api/approvals";
import { getCompanies } from "@/lib/api/companies";
import { getInsights } from "@/lib/api/insights";
import { GET as approvalsRoute } from "@/app/api/approvals/route";
import { GET as companiesRoute } from "@/app/api/companies/route";
import { GET as insightsRoute } from "@/app/api/insights/route";

describe("lib/api read-view data-access", () => {
  it("getApprovals returns the 6-approval queue", () => {
    const a = getApprovals();
    expect(a).toHaveLength(6);
    expect(a.find((x) => x.id === "a5")?.unverified).toBe(true);
  });

  it("getCompanies returns the 10-company registry", () => {
    const c = getCompanies();
    expect(c).toHaveLength(10);
    expect(c.find((x) => x.name === "Sereact")?.conf).toBe(64);
  });

  it("getInsights returns the insights aggregate", () => {
    const i = getInsights();
    expect(i.totalAnalysed).toBe(312);
    expect(i.lowConfExcluded).toBe(24);
    expect(i.skillDemand).toHaveLength(7);
  });

  it("the refactored routes still return the same shapes", async () => {
    expect(await approvalsRoute().json()).toHaveLength(6);
    expect(await companiesRoute().json()).toHaveLength(10);
    expect((await insightsRoute().json()).totalAnalysed).toBe(312);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/lib/api/read-views.test.ts`
Expected: FAIL — cannot resolve `@/lib/api/approvals`.

- [ ] **Step 3: Create the data-access functions**

Create `apps/web/src/lib/api/approvals.ts`:

```ts
import type { Approval } from "@specula/shared-types";
import { approvals } from "@/lib/seed/data";

// M2: BFF → FastAPI.
export function getApprovals(): Approval[] {
  return approvals.slice();
}
```

Create `apps/web/src/lib/api/companies.ts`:

```ts
import type { Company } from "@specula/shared-types";
import { companies } from "@/lib/seed/data";

export function getCompanies(): Company[] {
  return companies.slice();
}
```

Create `apps/web/src/lib/api/insights.ts`:

```ts
import type { Insights } from "@specula/shared-types";
import { insights } from "@/lib/seed/data";

export function getInsights(): Insights {
  return insights;
}
```

- [ ] **Step 4: Refactor the three routes to call the data-access layer**

Replace `apps/web/src/app/api/approvals/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getApprovals } from "@/lib/api/approvals";

export function GET(): NextResponse {
  return NextResponse.json(getApprovals());
}
```

Replace `apps/web/src/app/api/companies/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getCompanies } from "@/lib/api/companies";

export function GET(): NextResponse {
  return NextResponse.json(getCompanies());
}
```

Replace `apps/web/src/app/api/insights/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getInsights } from "@/lib/api/insights";

export function GET(): NextResponse {
  return NextResponse.json(getInsights());
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/lib/api/read-views.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/api apps/web/src/app/api
git commit -m "refactor(web): lib/api data-access for approvals/companies/insights; routes call it (M1b-2)"
```

---

### Task 2: Approval queue (ApprovalCard + ApprovalsView + page)

**Files:**
- Create: `apps/web/src/components/approvals/approval-card.tsx`, `apps/web/src/components/approvals/approvals-view.tsx`
- Test: `apps/web/src/components/approvals/approvals-view.test.tsx`
- Modify: `apps/web/src/app/(app)/approvals/page.tsx`

**Interfaces:**
- Consumes: `Approval` from `@specula/shared-types`; `Chip`, `Tag`, `Button` atoms; `getApprovals` from `@/lib/api/approvals` (page + test).
- Produces:
  - `ApprovalCard({ approval: Approval })`
  - `ApprovalsView({ approvals: Approval[] })`

> **Note:** ApprovalCard + ApprovalsView are **server components** (no `"use client"`) — the actions are inert (M2), so there's no state or handler. The action buttons render with NO `onClick`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/approvals/approvals-view.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ApprovalsView } from "@/components/approvals/approvals-view";
import { ApprovalCard } from "@/components/approvals/approval-card";
import { getApprovals } from "@/lib/api/approvals";

afterEach(cleanup);
const approvals = getApprovals();
const verified = approvals.find((a) => !a.unverified)!;
const unverified = approvals.find((a) => a.unverified)!;

describe("ApprovalsView", () => {
  it("renders the DERIVED pending count and 0 approved (inert)", () => {
    const { container } = render(<ApprovalsView approvals={approvals} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("6");
    expect(header).toHaveTextContent("pending");
    expect(header).toHaveTextContent("0");
    expect(header).toHaveTextContent("approved");
  });

  it("renders one card per approval", () => {
    const { container } = render(<ApprovalsView approvals={approvals} />);
    expect(container.querySelectorAll("[data-appr]")).toHaveLength(6);
  });
});

describe("ApprovalCard", () => {
  it("renders name, domain, why, roles chip, ATS, and query", () => {
    render(<ApprovalCard approval={verified} />);
    expect(screen.getByText(verified.name)).toBeInTheDocument();
    expect(screen.getByText(verified.domain)).toBeInTheDocument();
    expect(screen.getByText(verified.why)).toBeInTheDocument();
    expect(screen.getByText(`${verified.roles} open`)).toBeInTheDocument();
    expect(screen.getByText(verified.ats)).toBeInTheDocument();
    expect(
      screen.getByText(`⌕ found via "${verified.query}"`),
    ).toBeInTheDocument();
  });

  it("shows the HQ chip for a verified approval", () => {
    render(<ApprovalCard approval={verified} />);
    expect(screen.getByText(`HQ ${verified.hq}`)).toBeInTheDocument();
    expect(screen.queryByText(/origin unverified/)).toBeNull();
  });

  it("shows the unverified flag instead of the HQ chip when unverified", () => {
    render(<ApprovalCard approval={unverified} />);
    expect(screen.getByText("⚐ HQ origin unverified")).toBeInTheDocument();
    expect(screen.queryByText(`HQ ${unverified.hq}`)).toBeNull();
  });

  it("renders the three action buttons (inert — no handlers)", () => {
    render(<ApprovalCard approval={verified} />);
    expect(screen.getByText("✓ Approve")).toBeInTheDocument();
    expect(screen.getByText("✕ Reject")).toBeInTheDocument();
    expect(screen.getByText("☾")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/approvals/approvals-view.test.tsx`
Expected: FAIL — cannot resolve `@/components/approvals/approvals-view`.

- [ ] **Step 3: Implement ApprovalCard (from `pipeline.jsx:5–34` + `views.css` `.appr*`)**

Create `apps/web/src/components/approvals/approval-card.tsx`:

```tsx
import type { Approval } from "@specula/shared-types";
import { Chip } from "@/components/atoms/chip";
import { Tag } from "@/components/atoms/tag";
import { Button } from "@/components/atoms/button";

export function ApprovalCard({ approval: c }: { approval: Approval }) {
  return (
    <div
      data-appr={c.id}
      className="flex flex-col gap-[13px] rounded-[14px] border border-rule bg-card p-[18px_20px] shadow-card"
    >
      <div className="flex items-start gap-[12px]">
        <div className="flex h-[40px] w-[40px] shrink-0 items-center justify-center rounded-[9px] bg-panel-2 font-mono text-[13px] font-semibold text-ink">
          {c.logo}
        </div>
        <div className="flex-1">
          <div className="text-[15px] font-semibold">
            {c.name} <span className="text-[13px]">{c.flag}</span>
          </div>
          <div className="mt-[2px] font-mono text-[11px] text-ink-2">
            {c.domain}
          </div>
        </div>
        <Chip mono>{c.roles} open</Chip>
      </div>
      <p className="text-[12.5px] leading-[1.5] text-ink-2">{c.why}</p>
      <div className="flex flex-wrap gap-[7px]">
        <span className="rounded-[5px] bg-panel-2 px-[8px] py-[3px] font-mono text-[11px] text-ink">
          {c.ats}
        </span>
        {c.unverified ? (
          <Tag variant="flag">⚐ HQ origin unverified</Tag>
        ) : (
          <Chip mono>HQ {c.hq}</Chip>
        )}
      </div>
      <div className="flex items-center gap-[6px] font-mono text-[10.5px] text-ink-3">
        ⌕ found via &quot;{c.query}&quot;
      </div>
      <div className="mt-[2px] flex gap-[8px]">
        <Button variant="accent" className="flex-1 justify-center">
          ✓ Approve
        </Button>
        <Button className="flex-1 justify-center">✕ Reject</Button>
        <Button title="Snooze">☾</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement ApprovalsView (from `pipeline.jsx:36–61` + `specula.css` `.vhead*` + `views.css` `.appr-grid`/`.empty`)**

Create `apps/web/src/components/approvals/approvals-view.tsx`:

```tsx
import type { Approval } from "@specula/shared-types";
import { ApprovalCard } from "@/components/approvals/approval-card";

export function ApprovalsView({ approvals }: { approvals: Approval[] }) {
  return (
    <section
      data-screen-label="approvals"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Approval queue
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Discovery surfaces candidate companies against your targeting.
            Approve once — on approval each is enriched (HQ country + confidence,
            rough comp) and added to the registry. Rejections suppress repeats.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">
              {approvals.length}
            </b>{" "}
            pending
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">0</b> approved
          </div>
        </div>
      </header>

      {approvals.length === 0 ? (
        <div className="px-[20px] py-[80px] text-center text-ink-2">
          <div className="mb-[14px] text-[34px] opacity-40">✓</div>
          Queue clear. Next discovery run is scheduled for Monday.
        </div>
      ) : (
        <div className="mt-[20px] grid grid-cols-2 gap-[14px]">
          {approvals.map((c) => (
            <ApprovalCard key={c.id} approval={c} />
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Wire the RSC page**

Replace `apps/web/src/app/(app)/approvals/page.tsx` with:

```tsx
import { ApprovalsView } from "@/components/approvals/approvals-view";
import { getApprovals } from "@/lib/api/approvals";

export default function ApprovalsPage() {
  return <ApprovalsView approvals={getApprovals()} />;
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pnpm test src/components/approvals/approvals-view.test.tsx`
Expected: PASS (7 tests).

- [ ] **Step 7: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/approvals "apps/web/src/app/(app)/approvals/page.tsx"
git commit -m "feat(web): Approval queue view (cards, inert actions) (M1b-2)"
```

---

### Task 3: Companies registry (Chip `strong` variant + CompaniesView + page)

**Files:**
- Modify: `apps/web/src/components/atoms/chip.tsx`
- Create: `apps/web/src/components/companies/companies-view.tsx`
- Test: `apps/web/src/components/atoms/chip.test.tsx`, `apps/web/src/components/companies/companies-view.test.tsx`
- Modify: `apps/web/src/app/(app)/companies/page.tsx`

**Interfaces:**
- Consumes: `Company` from `@specula/shared-types`; `Chip` (extended), `Toggle` atoms; `getCompanies` from `@/lib/api/companies` (page + test).
- Produces:
  - `Chip({ children, mono?, strong? })` — adds `strong?: boolean`.
  - `CompaniesView({ companies: Company[] })` — `"use client"` (holds the filter string).

> **Note:** CompaniesView IS `"use client"` (the live filter uses `useState`). The tracking `Toggle` is inert — pass `on={true}` and a no-op `onChange={() => {}}` (the atom requires `onChange`; being controlled with a no-op keeps it visually on and non-mutating). The comp-est chip uses the new `<Chip strong>`.

- [ ] **Step 1: Write the failing Chip test**

Create `apps/web/src/components/atoms/chip.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { Chip } from "@/components/atoms/chip";

afterEach(cleanup);

describe("Chip", () => {
  it("default uses ink-2 text + rule border", () => {
    render(<Chip>x</Chip>);
    const el = screen.getByText("x");
    expect(el.className).toContain("text-ink-2");
    expect(el.className).toContain("border-rule");
    expect(el.className).not.toContain("text-ink ");
  });

  it("strong uses ink text + rule-2 border", () => {
    render(<Chip strong>y</Chip>);
    const el = screen.getByText("y");
    expect(el.className).toContain("text-ink");
    expect(el.className).toContain("border-rule-2");
  });

  it("mono and strong compose", () => {
    render(
      <Chip mono strong>
        z
      </Chip>,
    );
    const el = screen.getByText("z");
    expect(el.className).toContain("font-mono");
    expect(el.className).toContain("border-rule-2");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/atoms/chip.test.tsx`
Expected: FAIL — the `strong` test fails (no such prop; border/text still default).

- [ ] **Step 3: Extend the Chip atom**

Replace `apps/web/src/components/atoms/chip.tsx` with:

```tsx
export function Chip({
  children,
  mono = false,
  strong = false,
}: {
  children: React.ReactNode;
  mono?: boolean;
  strong?: boolean;
}) {
  return (
    <span
      className={`rounded-[6px] border bg-paper px-[9px] py-[3px] ${
        strong ? "border-rule-2 text-ink" : "border-rule text-ink-2"
      } ${mono ? "font-mono text-[10.5px]" : "text-[11.5px]"}`}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 4: Run the Chip test to verify it passes**

Run: `pnpm test src/components/atoms/chip.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing CompaniesView test**

Create `apps/web/src/components/companies/companies-view.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CompaniesView } from "@/components/companies/companies-view";
import { getCompanies } from "@/lib/api/companies";

afterEach(cleanup);
const companies = getCompanies();

describe("CompaniesView", () => {
  it("renders DERIVED tracked count (10) and open-roles sum (67)", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("10");
    expect(header).toHaveTextContent("tracked");
    expect(header).toHaveTextContent("67");
    expect(header).toHaveTextContent("open roles");
  });

  it("renders one table row per company", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(10);
  });

  it("flags HQ confidence < 80 with warn styling + ⚐, and not for >= 80", () => {
    render(<CompaniesView companies={companies} />);
    // Sereact = 64 (<80): warn conf cell with ⚐
    expect(screen.getByText(/64% ⚐/)).toBeInTheDocument();
    // Mistral AI = 98 (>=80): plain, no ⚐
    expect(screen.getByText("98%")).toBeInTheDocument();
  });

  it("filters rows by name or HQ (case-insensitive) and updates the N of M count", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    const input = screen.getByPlaceholderText(/Filter by name or HQ/);
    fireEvent.change(input, { target: { value: "france" } });
    // France HQ: Mistral AI, Qonto, Pigment = 3
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(screen.getByText("3 of 10")).toBeInTheDocument();
  });

  it("renders the comp-est chip and an inert tracking toggle per row", () => {
    const { container } = render(<CompaniesView companies={companies} />);
    // Toggle atom renders role="switch"; one per row
    expect(container.querySelectorAll('[role="switch"]')).toHaveLength(10);
    expect(screen.getAllByText("€€€").length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pnpm test src/components/companies/companies-view.test.tsx`
Expected: FAIL — cannot resolve `@/components/companies/companies-view`.

- [ ] **Step 7: Implement CompaniesView (from `pipeline.jsx:63–117` + `views.css` `.tbl*`/`.conf*` + `.toolbar`)**

Create `apps/web/src/components/companies/companies-view.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { Company } from "@specula/shared-types";
import { Chip } from "@/components/atoms/chip";
import { Toggle } from "@/components/atoms/toggle";

export function CompaniesView({ companies }: { companies: Company[] }) {
  const [q, setQ] = useState("");
  const query = q.toLowerCase();
  const rows = companies.filter(
    (c) =>
      c.name.toLowerCase().includes(query) ||
      c.hq.toLowerCase().includes(query),
  );
  const totalOpen = companies.reduce((s, c) => s + c.open, 0);

  return (
    <section
      data-screen-label="companies"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Companies
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Approved companies in the registry — ATS provider and feed, enriched
            HQ country with confidence, and a rough comp estimate (informational
            only). Global across every lens.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">
              {companies.length}
            </b>{" "}
            tracked
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{totalOpen}</b>{" "}
            open roles
          </div>
        </div>
      </header>

      <div className="mt-[16px] mb-[6px] flex items-center justify-between font-mono text-[11px] text-ink-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by name or HQ country…"
          className="w-full max-w-[280px] rounded-[9px] border border-rule-2 bg-card px-[12px] py-[8px] font-body text-[13.5px] text-ink focus:border-ink focus:outline-none"
        />
        <span>
          {rows.length} of {companies.length}
        </span>
      </div>

      <table className="mt-[18px] w-full border-collapse">
        <thead>
          <tr>
            {[
              "Company",
              "ATS feed",
              "HQ country",
              "HQ confidence",
              "Open",
              "Comp est.",
              "Tracking",
            ].map((h) => (
              <th
                key={h}
                className="border-b border-rule px-[14px] pb-[11px] text-left font-mono text-[9.5px] font-normal uppercase tracking-[0.08em] text-ink-3"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const low = c.conf < 80;
            return (
              <tr key={c.name} className="transition-colors hover:bg-panel">
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <div className="flex items-center gap-[11px] font-semibold">
                    <div className="flex h-[30px] w-[30px] items-center justify-center rounded-[7px] bg-panel-2 font-mono text-[10px] font-semibold text-ink-2">
                      {c.logo}
                    </div>
                    <div>
                      <div>{c.name}</div>
                      <div className="mt-px font-mono text-[11px] font-normal text-ink-2">
                        {c.domain}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <span className="rounded-[5px] bg-panel-2 px-[8px] py-[3px] font-mono text-[11px] text-ink">
                    {c.ats}
                  </span>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  {c.flag} {c.hq}
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <span
                    className={`inline-flex items-center gap-[8px] font-mono text-[11.5px] ${low ? "text-warn" : ""}`}
                  >
                    <span className="h-[5px] w-[46px] overflow-hidden rounded-[3px] bg-panel-2">
                      <span
                        className={`block h-full ${low ? "bg-warn" : "bg-accent"}`}
                        style={{ width: `${c.conf}%` }}
                      />
                    </span>
                    {c.conf}%{low ? " ⚐" : ""}
                  </span>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle font-mono text-[13.5px]">
                  {c.open}
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <Chip strong>{c.comp}</Chip>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <Toggle on onChange={() => {}} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
```

- [ ] **Step 8: Wire the RSC page**

Replace `apps/web/src/app/(app)/companies/page.tsx` with:

```tsx
import { CompaniesView } from "@/components/companies/companies-view";
import { getCompanies } from "@/lib/api/companies";

export default function CompaniesPage() {
  return <CompaniesView companies={getCompanies()} />;
}
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pnpm test src/components/companies/companies-view.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 10: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green.

- [ ] **Step 11: Commit**

```bash
git add apps/web/src/components/atoms/chip.tsx apps/web/src/components/atoms/chip.test.tsx apps/web/src/components/companies "apps/web/src/app/(app)/companies/page.tsx"
git commit -m "feat(web): Companies registry (live filter, HQ-conf flag, Chip strong variant) (M1b-2)"
```

---

### Task 4: Insights (DemandTrend + InsightsView + page) + build gate

**Files:**
- Create: `apps/web/src/components/insights/demand-trend.tsx`, `apps/web/src/components/insights/insights-view.tsx`
- Test: `apps/web/src/components/insights/insights-view.test.tsx`
- Modify: `apps/web/src/app/(app)/insights/page.tsx`

**Interfaces:**
- Consumes: `Insights`, `Trend` from `@specula/shared-types`; `Tag` atom; `getInsights` from `@/lib/api/insights` (page + test).
- Produces:
  - `DemandTrend({ trend: Trend })`
  - `InsightsView({ insights: Insights })`

> **Note:** InsightsView + DemandTrend are **server components** (no `"use client"`). The period `<select>` is inert (`defaultValue`, no `onChange`). Every bar/segment renders at FINAL width (the `run`-gated grow + `useCountUp` are M1c) — the `analysed` number shows `insights.totalAnalysed` directly.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/insights/insights-view.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { InsightsView } from "@/components/insights/insights-view";
import { DemandTrend } from "@/components/insights/demand-trend";
import { getInsights } from "@/lib/api/insights";

afterEach(cleanup);
const insights = getInsights();

describe("InsightsView", () => {
  it("renders the low-confidence exclusion banner with the excluded count", () => {
    render(<InsightsView insights={insights} />);
    expect(
      screen.getByText(
        /24 low-confidence extractions excluded from every aggregate/,
      ),
    ).toBeInTheDocument();
  });

  it("renders the analysed total at its final value", () => {
    const { container } = render(<InsightsView insights={insights} />);
    expect(container.querySelector("header")).toHaveTextContent("312");
  });

  it("renders all six panels", () => {
    render(<InsightsView insights={insights} />);
    for (const title of [
      "Skill demand",
      "Demand drift",
      "Seniority mix",
      "Work-mode mix",
      "Salary distribution",
      "Most-active companies",
    ]) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
  });

  it("marks a gap skill and shows the salary display-only caption", () => {
    render(<InsightsView insights={insights} />);
    // Kubernetes has gap: true
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
    expect(screen.getAllByText("gap").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Never used to rank or filter/),
    ).toBeInTheDocument();
  });
});

describe("DemandTrend", () => {
  it("renders a column per week and a legend entry per series", () => {
    const { container } = render(<DemandTrend trend={insights.trend} />);
    expect(container.querySelectorAll("[data-trend-col]")).toHaveLength(8);
    // legend: one entry per series (3)
    expect(screen.getByText("LLM / RAG")).toBeInTheDocument();
    expect(screen.getByText("Inference / vLLM")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/insights/insights-view.test.tsx`
Expected: FAIL — cannot resolve `@/components/insights/insights-view`.

- [ ] **Step 3: Implement DemandTrend (from `intel.jsx:5–28` + `views.css` `.trend*`/`.legend`)**

Create `apps/web/src/components/insights/demand-trend.tsx`:

```tsx
import type { Trend } from "@specula/shared-types";

export function DemandTrend({ trend }: { trend: Trend }) {
  const totals = trend.weeks.map((_, wi) =>
    trend.series.reduce((s, ser) => s + ser.data[wi], 0),
  );
  const max = Math.max(...totals);
  return (
    <div>
      <div className="relative flex h-[150px] items-end gap-0 pt-[10px]">
        {trend.weeks.map((wk, wi) => (
          <div
            key={wk}
            data-trend-col
            className="flex h-full flex-1 flex-col items-center justify-end gap-[8px]"
          >
            <div className="flex h-full w-[60%] flex-col justify-end gap-[2px]">
              {trend.series.map((ser) => (
                <div
                  key={ser.name}
                  className="min-h-[2px] rounded-t-[2px]"
                  style={{
                    background: ser.color,
                    height: `${(ser.data[wi] / max) * 130}px`,
                  }}
                />
              ))}
            </div>
            <span className="font-mono text-[9px] text-ink-3">{wk}</span>
          </div>
        ))}
      </div>
      <div className="mt-[14px] flex gap-[16px] font-mono text-[10.5px] text-ink-2">
        {trend.series.map((s) => (
          <span key={s.name} className="flex items-center gap-[6px]">
            <i
              className="h-[9px] w-[9px] rounded-[2px]"
              style={{ background: s.color }}
            />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement InsightsView (from `intel.jsx:30–130` + `views.css` `.ins-grid`/`.panel*`/`.demand*`/`.mixbar`/`.salary*`)**

Create `apps/web/src/components/insights/insights-view.tsx`:

```tsx
import type { Insights } from "@specula/shared-types";
import { Tag } from "@/components/atoms/tag";
import { DemandTrend } from "@/components/insights/demand-trend";

function Panel({
  title,
  sub,
  children,
}: {
  title: string;
  sub: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[14px] border border-rule bg-card p-[20px_22px] shadow-card">
      <div className="mb-[18px] flex items-baseline justify-between">
        <span className="font-display text-[17px] font-semibold">{title}</span>
        <span className="font-mono text-[10.5px] text-ink-2">{sub}</span>
      </div>
      {children}
    </div>
  );
}

export function InsightsView({ insights: ins }: { insights: Insights }) {
  const seniorMax = Math.max(...ins.seniorityMix.map((s) => s.v));
  return (
    <section
      data-screen-label="insights"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Insights
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Personal market intelligence — aggregates over every structured
            posting you&apos;ve collected. Most trackers can&apos;t show this
            because they never parse the ads. Low-confidence extractions are
            excluded.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <select
            defaultValue="8w"
            aria-label="period"
            className="rounded-[6px] border border-rule-2 bg-card px-[9px] py-[5px] font-mono text-[12px] text-ink"
          >
            <option value="4w">Last 4 weeks</option>
            <option value="8w">Last 8 weeks</option>
            <option value="q">This quarter</option>
          </select>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">
              {ins.totalAnalysed}
            </b>{" "}
            analysed
          </div>
        </div>
      </header>

      <p className="mt-[16px] text-[12.5px] leading-[1.5] text-ink-2">
        ⚐ {ins.lowConfExcluded} low-confidence extractions excluded from every
        aggregate below. Treat trends as directional.
      </p>

      <div className="mt-[22px] grid grid-cols-2 gap-[18px]">
        <Panel title="Skill demand" sub="% of postings · Δ vs 8w ago">
          <div className="flex flex-col gap-[13px]">
            {ins.skillDemand.map((s) => (
              <div
                key={s.skill}
                className="grid grid-cols-[120px_1fr_64px] items-center gap-[12px]"
              >
                <span className="text-[12.5px] font-medium">
                  {s.skill}
                  {s.gap && (
                    <span className="ml-[6px] text-[9px]">
                      <Tag variant="flag">gap</Tag>
                    </span>
                  )}
                </span>
                <span className="h-[9px] overflow-hidden rounded-[3px] bg-panel-2">
                  <span
                    className={`block h-full rounded-[3px] ${s.up ? "bg-accent" : "bg-ink"}`}
                    style={{ width: `${s.pct}%` }}
                  />
                </span>
                <span
                  className={`text-right font-mono text-[11px] ${s.delta >= 0 ? "text-accent" : "text-warn"}`}
                >
                  {s.delta >= 0 ? "▲" : "▼"} {Math.abs(s.delta)}%
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Demand drift" sub="stacked, weekly">
          <DemandTrend trend={ins.trend} />
        </Panel>

        <Panel title="Seniority mix" sub="% of pool">
          <div className="flex flex-col gap-[13px]">
            {ins.seniorityMix.map((s) => (
              <div
                key={s.k}
                className="grid grid-cols-[120px_1fr_64px] items-center gap-[12px]"
              >
                <span className="text-[12.5px] font-medium">{s.k}</span>
                <span className="h-[9px] overflow-hidden rounded-[3px] bg-panel-2">
                  <span
                    className="block h-full rounded-[3px]"
                    style={{
                      width: `${(s.v / seniorMax) * 100}%`,
                      background:
                        s.k === "Senior" ? "var(--accent)" : "var(--ink)",
                    }}
                  />
                </span>
                <span className="text-right font-mono text-[11px] text-ink-2">
                  {s.v}%
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Work-mode mix" sub="& its drift">
          <div className="mb-[14px] flex h-[38px] overflow-hidden rounded-[9px]">
            {ins.modeMix.map((m) => (
              <div
                key={m.k}
                className="flex items-center justify-center font-mono text-[11px] font-semibold text-white"
                style={{ flex: m.v, background: m.color }}
              >
                {m.v}%
              </div>
            ))}
          </div>
          <div className="flex gap-[16px] font-mono text-[10.5px] text-ink-2">
            {ins.modeMix.map((m) => (
              <span key={m.k} className="flex items-center gap-[6px]">
                <i
                  className="h-[9px] w-[9px] rounded-[2px]"
                  style={{ background: m.color }}
                />
                {m.k}
              </span>
            ))}
          </div>
          <p className="mt-[14px] text-[12.5px] leading-[1.5] text-ink-2">
            Remote share is up{" "}
            <b className="text-accent-ink">+5pts</b> over 8 weeks — good news for
            your remote-EU lens.
          </p>
        </Panel>

        <Panel title="Salary distribution" sub="where listed · informational">
          <div className="flex flex-col gap-[11px]">
            {ins.salary.map((s) => (
              <div
                key={s.band}
                className="grid grid-cols-[90px_1fr] items-center gap-[12px] text-[12.5px]"
              >
                <span className="font-mono text-[12px]">{s.band}</span>
                <span className="relative h-[22px] rounded-[5px] bg-accent-bg">
                  <span
                    className="absolute h-full rounded-[5px] bg-accent opacity-[0.85]"
                    style={{ left: `${s.lo}%`, width: `${s.hi - s.lo}%` }}
                  />
                </span>
              </div>
            ))}
          </div>
          <p className="mt-[14px] text-[12.5px] leading-[1.5] text-ink-2">
            Only ~38% of ads list pay. Never used to rank or filter — shown for
            context only.
          </p>
        </Panel>

        <Panel title="Most-active companies" sub="postings, 8w">
          <div className="flex flex-col gap-[13px]">
            {ins.activeCompanies.map((c, i) => (
              <div
                key={c.name}
                className="grid grid-cols-[120px_1fr_30px] items-center gap-[12px]"
              >
                <span className="text-[12.5px] font-medium">{c.name}</span>
                <span className="h-[9px] overflow-hidden rounded-[3px] bg-panel-2">
                  <span
                    className="block h-full rounded-[3px]"
                    style={{
                      width: `${(c.n / 12) * 100}%`,
                      background: i === 0 ? "var(--accent)" : "var(--ink)",
                    }}
                  />
                </span>
                <span className="text-right font-mono text-[11px] text-ink-2">
                  {c.n}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Wire the RSC page**

Replace `apps/web/src/app/(app)/insights/page.tsx` with:

```tsx
import { InsightsView } from "@/components/insights/insights-view";
import { getInsights } from "@/lib/api/insights";

export default function InsightsPage() {
  return <InsightsView insights={getInsights()} />;
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pnpm test src/components/insights/insights-view.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 7: Run all gates + build**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check && pnpm build`
Expected: all green — full Vitest suite passes, `next build` compiles (the `/approvals`, `/companies`, `/insights` routes now render their views). If `pnpm build` fails with a TLS/cert error (`SELF_SIGNED_CERT_IN_CHAIN`), re-run as `NODE_EXTRA_CA_CERTS="$HOME/.corp-ca.pem" pnpm build` (corporate proxy; the only sanctioned workaround — do not disable TLS verification).

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/insights "apps/web/src/app/(app)/insights/page.tsx"
git commit -m "feat(web): Insights dashboard (six CSS-chart panels, static) (M1b-2)"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** Task 1 → §2 data-access + §3 route refactor. Task 2 → §4 Approval queue (cards, inert actions, derived pending). Task 3 → §5 Companies (derived tracked/open, live filter, HQ-conf ⚐<80, comp chip display-only, inert toggle) + §7 Chip `strong`. Task 4 → §6 Insights (banner, six panels, salary caption) + the build gate + §8 acceptance. Deferred items honored: no animations (final widths), no persisting mutations (inert buttons/toggle/select).
- **RSC-first refinement:** Approvals + Insights are server components (no interactivity); only Companies is `"use client"` (filter). This is the spec's §3 data-flow made precise — no unnecessary client boundary.
- **Type consistency:** the data-access signatures in Task 1 (`getApprovals`/`getCompanies`/`getInsights`) are used verbatim by Tasks 2–4's pages + test fixtures. `Approval`/`Company`/`Insights`/`Trend` match `@specula/shared-types`. `Chip`'s new `strong?` prop is additive (Task 3) and used only by CompaniesView.
- **Derived counts** asserted against regression: Approvals 6 pending (Task 2), Companies 10 tracked / 67 open (Task 3), Insights 312 analysed / 24 excluded (Task 4).
- **Inert-control pattern:** action Buttons have no `onClick`; the Toggle is controlled `on` + no-op `onChange`; the period `<select>` is uncontrolled `defaultValue` with no `onChange`. None mutate.
- **No new E2E** — auth-gated views; the unauth redirect is already covered (M0b).
