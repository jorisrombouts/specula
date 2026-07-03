# M1b-3 — Config forms (Profiles · Candidate · Targeting) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the prototype's three config/edit views — Search profiles, Candidate profile, Targeting — to typed React against the M1a seed/atoms, with client-local live editing (TagEditor add/remove + lens toggles work in-browser, no persistence) as the exact shape M2 converts to persistence.

**Architecture:** Follows the M1b-1 JobsView pattern: a typed `lib/api/` data-access layer wraps the seed (`getTargeting`/`getSkillsGap` new; `getCandidate`/`getLenses` reused), and each RSC page passes data to a client view. All three views are `"use client"` because they hold editable local state (lens toggles / skills / tag fields).

**Tech Stack:** Next.js 16 (App Router, RSC + client islands), React 19, TypeScript strict, Tailwind v4 (arbitrary values translating `views.css`/`specula.css`), Vitest + @testing-library/react (jsdom), `@specula/shared-types`.

## Global Constraints

- **Next.js 16, TypeScript strict, Tailwind-native.** Rebuild each prototype component in Tailwind arbitrary-value classes translated from `prototype/specula/views.css` + `specula.css`. Do **not** import prototype CSS. Match the established idiom + theme tokens in `apps/web/src/app/globals.css` (`paper`, `panel`, `panel-2`, `card`, `ink`, `ink-2`, `ink-3`, `rule`, `rule-2`, `accent`, `accent-bg`, `accent-ink`, `warn`; `font-display`/`font-body`/`font-mono`; `shadow-card`). Prototype `var(--rule-2)` → Tailwind `rule-2`, etc.
- **Interactivity: LIVE client-local, NOT persisted.** Each view holds `useState(seedValues)`; `TagEditor` add/remove and lens `Toggle` update local state (reset on reload). Text inputs + textarea are **uncontrolled** (`defaultValue`). This is the prototype's behavior and the M2 shape. Backend-action buttons ("+ New profile", "✎ Draft a tailored CV bullet") render with **NO `onClick`** (inert → M2).
- **Counts DERIVED, never hard-coded.** Profiles header `{active}/{total}` from the lens state; each lens card's `N roles · M new` from `LensSummary.count`/`.isNew`. Never cosmetic constants.
- **Salary never a rule/signal; geography lives in profiles.** The Targeting info banner states both verbatim; Targeting has NO geography/mode fields.
- **Compose the built atoms:** `TagEditor` (`{ values, onChange, kind }`), `Toggle` (`{ on, onChange }`), `Button`, `Chip` from `@/components/atoms/*`. Do NOT reimplement them. `TagEditor` add/remove is already atom-tested (M1a) — the view tests verify the WIRING, not the atom internals.
- **No animations (M1c).** **No new E2E** — auth-gated views; the unauth redirect is already covered. Testing = data-access unit + Vitest component tests (`import { describe, it, expect, afterEach } from "vitest"`; `render/screen/fireEvent/cleanup/within` from `@testing-library/react`; `afterEach(cleanup)`).
- **Sources of truth:** `config.jsx`, `views.css`/`specula.css`, spec `docs/superpowers/specs/2026-07-03-m1b-3-config-forms-design.md`. All commands run from `apps/web`.
- **Seed facts (fixed by the M1a seed):** lenses = 5 (`all` active, `remote`/`foreign`/`spain` active, `berlin` **inactive**) → **4 active / 5 total**, 4 cards (excl. `all`). Candidate: initials `JV`, title `Data Scientist / ML Engineer`, location `Amsterdam, NL`, years `6`. skillsGap = 4 entries (Kubernetes 6×, …).

---

### Task 1: Data-access (`getTargeting` + `getSkillsGap`) + `/api/targeting` refactor

**Files:**
- Create: `apps/web/src/lib/api/targeting.ts`, `apps/web/src/lib/api/skills-gap.ts`
- Test: `apps/web/src/lib/api/config.test.ts`
- Modify: `apps/web/src/app/api/targeting/route.ts`

**Interfaces:**
- Consumes: `targeting`, `skillsGap` from `@/lib/seed/data`; types from `@specula/shared-types`.
- Produces:
  - `getTargeting(): Targeting`
  - `getSkillsGap(): SkillsGap[]`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/api/config.test.ts`:

```tsx
import { describe, it, expect } from "vitest";
import { getTargeting } from "@/lib/api/targeting";
import { getSkillsGap } from "@/lib/api/skills-gap";
import { GET as targetingRoute } from "@/app/api/targeting/route";

describe("lib/api config data-access", () => {
  it("getTargeting returns the targeting baseline", () => {
    const t = getTargeting();
    expect(t.roleTitles.length).toBeGreaterThan(0);
    expect(t.seniority.length).toBeGreaterThan(0);
  });

  it("getSkillsGap returns the skills-gap list", () => {
    const g = getSkillsGap();
    expect(g.length).toBeGreaterThan(0);
    expect(g[0]).toHaveProperty("roles");
    expect(g[0]).toHaveProperty("note");
  });

  it("the refactored /api/targeting route still returns the same shape", async () => {
    const body = await targetingRoute().json();
    expect(body.roleTitles).toEqual(getTargeting().roleTitles);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/lib/api/config.test.ts`
Expected: FAIL — cannot resolve `@/lib/api/targeting`.

- [ ] **Step 3: Create the data-access functions**

Create `apps/web/src/lib/api/targeting.ts`:

```ts
import type { Targeting } from "@specula/shared-types";
import { targeting } from "@/lib/seed/data";

// M2: BFF → FastAPI.
export function getTargeting(): Targeting {
  return targeting;
}
```

Create `apps/web/src/lib/api/skills-gap.ts`:

```ts
import type { SkillsGap } from "@specula/shared-types";
import { skillsGap } from "@/lib/seed/data";

export function getSkillsGap(): SkillsGap[] {
  return skillsGap.slice();
}
```

- [ ] **Step 4: Refactor the `/api/targeting` route**

Replace `apps/web/src/app/api/targeting/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getTargeting } from "@/lib/api/targeting";

export function GET(): NextResponse {
  return NextResponse.json(getTargeting());
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/lib/api/config.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/api/targeting.ts apps/web/src/lib/api/skills-gap.ts apps/web/src/lib/api/config.test.ts apps/web/src/app/api/targeting/route.ts
git commit -m "refactor(web): getTargeting + getSkillsGap data-access; /api/targeting calls it (M1b-3)"
```

---

### Task 2: Search profiles (ProfilesView + page)

**Files:**
- Create: `apps/web/src/components/profiles/profiles-view.tsx`
- Test: `apps/web/src/components/profiles/profiles-view.test.tsx`
- Modify: `apps/web/src/app/(app)/profiles/page.tsx`

**Interfaces:**
- Consumes: `LensSummary` from `@specula/shared-types`; `Toggle`, `Button` atoms; `getLenses` from `@/lib/api/lenses` (page + test).
- Produces: `ProfilesView({ lenses: LensSummary[] })` — `"use client"`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/profiles/profiles-view.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { ProfilesView } from "@/components/profiles/profiles-view";
import { getLenses } from "@/lib/api/lenses";

afterEach(cleanup);
const lenses = getLenses();

describe("ProfilesView", () => {
  it("shows DERIVED active/total (4 active / 5 total) and 4 cards (excludes 'all')", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("4");
    expect(header).toHaveTextContent("active");
    expect(header).toHaveTextContent("5");
    expect(header).toHaveTextContent("total");
    expect(container.querySelectorAll("[data-lens]")).toHaveLength(4);
    expect(container.querySelector('[data-lens="all"]')).toBeNull();
  });

  it("renders a lens card's DERIVED count badge + hard rules", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const remote = lenses.find((l) => l.id === "remote")!;
    const card = container.querySelector('[data-lens="remote"]') as HTMLElement;
    expect(
      within(card).getByText(`${remote.count} roles · ${remote.isNew} new`),
    ).toBeInTheDocument();
    expect(within(card).getByText(remote.scope)).toBeInTheDocument();
  });

  it("toggling a lens flips its active state locally", () => {
    const { container } = render(<ProfilesView lenses={lenses} />);
    const berlin = container.querySelector('[data-lens="berlin"]') as HTMLElement;
    expect(berlin.getAttribute("data-active")).toBe("false"); // seed: berlin inactive
    fireEvent.click(within(berlin).getByRole("switch"));
    expect(
      container.querySelector('[data-lens="berlin"]')!.getAttribute("data-active"),
    ).toBe("true");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/profiles/profiles-view.test.tsx`
Expected: FAIL — cannot resolve `@/components/profiles/profiles-view`.

- [ ] **Step 3: Implement ProfilesView (from `config.jsx:24–67` + `views.css` `.lens-cards`/`.lcard*`/`.rule-*`/`.seed*`)**

Create `apps/web/src/components/profiles/profiles-view.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { LensSummary } from "@specula/shared-types";
import { Toggle } from "@/components/atoms/toggle";
import { Button } from "@/components/atoms/button";

function RuleItem({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: string;
  muted?: boolean;
}) {
  return (
    <div>
      <div className="mb-[6px] font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">
        {label}
      </div>
      <div className={`text-[13px] ${muted ? "text-ink-2" : "text-ink"}`}>
        {value}
      </div>
    </div>
  );
}

export function ProfilesView({ lenses: seed }: { lenses: LensSummary[] }) {
  const [lenses, setLenses] = useState(seed);
  const toggle = (id: string) =>
    setLenses((ls) =>
      ls.map((l) => (l.id === id ? { ...l, active: !l.active } : l)),
    );
  const active = lenses.filter((l) => l.active).length;
  const cards = lenses.filter((l) => l.id !== "all");

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
            lens re-scopes the Jobs view and re-scores it on location.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">{active}</b> active
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{lenses.length}</b>{" "}
            total
          </div>
        </div>
      </header>

      <div className="mt-[22px] flex flex-col gap-[13px]">
        {cards.map((l) => (
          <div
            key={l.id}
            data-lens={l.id}
            data-active={l.active}
            className={`rounded-[14px] border border-rule bg-card p-[18px_22px] shadow-card transition-colors hover:border-rule-2 ${l.active ? "" : "opacity-60"}`}
          >
            <div className="mb-[14px] flex items-center gap-[14px]">
              <span className="font-display text-[19px] font-semibold">
                {l.name}
              </span>
              <span className="font-mono text-[10px] text-ink-2">
                {l.count} roles · {l.isNew} new
              </span>
              <span className="ml-auto">
                <Toggle on={l.active} onChange={() => toggle(l.id)} />
              </span>
            </div>
            <div className="grid grid-cols-3 gap-[16px]">
              <RuleItem label="Location scope · hard" value={l.scope} />
              <RuleItem label="Work mode · hard" value={l.modes.join(" / ")} />
              <RuleItem label="Origin rule · hard" value={l.origin} />
            </div>
            <div className="mt-[16px] grid grid-cols-2 gap-[16px]">
              <RuleItem label="Focus · soft signal" value={l.focus || "—"} muted />
              <div>
                <div className="mb-[6px] font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">
                  Discovery seeds · auto
                </div>
                <div className="mt-[6px] flex flex-wrap gap-[6px]">
                  {l.seeds.map((s) => (
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
        ))}
      </div>
      <Button className="mt-[16px]">+ New profile</Button>
    </section>
  );
}
```

- [ ] **Step 4: Wire the RSC page**

Replace `apps/web/src/app/(app)/profiles/page.tsx` with:

```tsx
import { ProfilesView } from "@/components/profiles/profiles-view";
import { getLenses } from "@/lib/api/lenses";

export default function ProfilesPage() {
  return <ProfilesView lenses={getLenses()} />;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/components/profiles/profiles-view.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/profiles "apps/web/src/app/(app)/profiles/page.tsx"
git commit -m "feat(web): Search profiles view (lens cards, live toggles, derived counts) (M1b-3)"
```

---

### Task 3: Candidate profile (shared `Field` + CandidateView + page)

**Files:**
- Create: `apps/web/src/components/config/field.tsx`, `apps/web/src/components/candidate/candidate-view.tsx`
- Test: `apps/web/src/components/candidate/candidate-view.test.tsx`
- Modify: `apps/web/src/app/(app)/candidate/page.tsx`

**Interfaces:**
- Consumes: `Candidate`, `SkillsGap` from `@specula/shared-types`; `TagEditor`, `Button` atoms; `getCandidate` from `@/lib/api/candidate` + `getSkillsGap` from `@/lib/api/skills-gap` (page + test).
- Produces:
  - `Field({ label: string, children: React.ReactNode })` — shared form-field wrapper (Task 4 reuses it).
  - `CandidateView({ candidate: Candidate, skillsGap: SkillsGap[] })` — `"use client"`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/candidate/candidate-view.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CandidateView } from "@/components/candidate/candidate-view";
import { getCandidate } from "@/lib/api/candidate";
import { getSkillsGap } from "@/lib/api/skills-gap";

afterEach(cleanup);
const c = getCandidate();
const gap = getSkillsGap();

describe("CandidateView", () => {
  it("renders the seed avatar initials + field values", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByText(c.initials)).toBeInTheDocument(); // "JV" from seed, not session
    expect(screen.getByDisplayValue(c.title)).toBeInTheDocument();
    expect(screen.getByDisplayValue(c.location)).toBeInTheDocument();
  });

  it("renders the skills-gap panel with a gap item", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByText("Skills gap")).toBeInTheDocument();
    expect(screen.getByText(gap[0].skill)).toBeInTheDocument();
    expect(screen.getByText(`${gap[0].roles}×`)).toBeInTheDocument();
  });

  it("removes and adds a skill tag locally (wiring)", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const first = c.skills[0];
    // remove the first skill chip via its × (aria-label from the TagEditor atom)
    fireEvent.click(screen.getByLabelText(`remove ${first}`));
    expect(screen.queryByLabelText(`remove ${first}`)).toBeNull();
    // add a new skill: the single "+ add" is the Skills TagEditor's
    fireEvent.click(screen.getByText("+ add"));
    const input = document.activeElement as HTMLInputElement; // autofocused add input
    fireEvent.change(input, { target: { value: "GraphQL" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByText("GraphQL")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/candidate/candidate-view.test.tsx`
Expected: FAIL — cannot resolve `@/components/candidate/candidate-view`.

- [ ] **Step 3: Create the shared `Field` wrapper**

Create `apps/web/src/components/config/field.tsx`:

```tsx
export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-[20px]">
      <label className="mb-[9px] block font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
        {label}
      </label>
      {children}
    </div>
  );
}
```

- [ ] **Step 4: Implement CandidateView (from `config.jsx:70–138` + `specula.css` `.me-av` + `views.css` `.form-grid`/`.field*`/`.input`/`.tagchip`/`.gap-*`/`.panel*`)**

Create `apps/web/src/components/candidate/candidate-view.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { Candidate, SkillsGap } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Button } from "@/components/atoms/button";
import { Field } from "@/components/config/field";

const INPUT =
  "w-full rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] text-ink focus:border-ink focus:outline-none";
const CHIP =
  "mb-2 block rounded-[7px] border border-rule bg-panel px-3 py-[6px] text-[12.5px] text-ink";

export function CandidateView({
  candidate: c,
  skillsGap,
}: {
  candidate: Candidate;
  skillsGap: SkillsGap[];
}) {
  const [skills, setSkills] = useState(c.skills);

  return (
    <section
      data-screen-label="candidate"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Candidate profile
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Who you are — fed to the model so every match reflects fit between
            you and the role. Kept explicit (a form, not a parsed CV) so you
            control exactly what you match against. Also powers skills-gap.
          </p>
        </div>
        <div className="flex h-[40px] w-[40px] items-center justify-center rounded-[9px] bg-ink font-mono text-[13px] font-semibold text-paper">
          {c.initials}
        </div>
      </header>

      <div className="mt-[24px] grid grid-cols-[1fr_320px] items-start gap-[26px]">
        <div>
          <Field label="Headline">
            <input className={INPUT} defaultValue={c.title} />
          </Field>
          <div className="grid grid-cols-2 gap-[16px]">
            <Field label="Location">
              <input className={INPUT} defaultValue={c.location} />
            </Field>
            <Field label="Work mode">
              <input className={INPUT} defaultValue={c.workMode} />
            </Field>
            <Field label="Years experience">
              <input className={INPUT} defaultValue={`${c.years} years`} />
            </Field>
            <Field label="Visa">
              <input className={INPUT} defaultValue={c.visa} />
            </Field>
          </div>
          <Field label="Skills · matched against required_skills">
            <TagEditor values={skills} onChange={setSkills} />
          </Field>
          <Field label="Projects">
            {c.projects.map((p) => (
              <div
                key={p.name}
                className="mb-2 block rounded-[7px] border border-rule-2 bg-card px-3 py-[6px] text-[12.5px] text-ink"
              >
                <b>{p.name}</b> <span className="text-ink-2">— {p.note}</span>
              </div>
            ))}
          </Field>
          <div className="grid grid-cols-2 gap-[16px]">
            <Field label="Experience">
              {c.experience.map((e) => (
                <div key={e.org} className={CHIP}>
                  <b>{e.role}</b> · {e.org}{" "}
                  <span className="font-mono text-[11px] text-ink-2">
                    {e.period}
                  </span>
                </div>
              ))}
            </Field>
            <Field label="Education & languages">
              <div className={CHIP}>{c.education}</div>
              <div className="flex flex-wrap gap-2">
                {c.languages.map((l) => (
                  <span
                    key={l}
                    className="rounded-[7px] border border-rule bg-panel px-3 py-[6px] text-[12.5px] text-ink"
                  >
                    {l}
                  </span>
                ))}
              </div>
            </Field>
          </div>
        </div>

        <div className="sticky top-0">
          <div className="rounded-[14px] border border-rule bg-card p-[20px_22px] shadow-card">
            <div className="mb-[18px] flex items-baseline justify-between">
              <span className="font-display text-[17px] font-semibold">
                Skills gap
              </span>
              <span className="font-mono text-[10.5px] text-ink-2">
                vs target roles
              </span>
            </div>
            <p className="mb-[6px] text-[12.5px] leading-[1.5] text-ink-2">
              Most-demanded skills across your target roles that aren&apos;t on
              your profile:
            </p>
            {skillsGap.map((g) => (
              <div
                key={g.skill}
                className="flex items-center gap-[11px] border-b border-rule py-[11px] last:border-b-0"
              >
                <span className="flex h-[38px] w-[42px] items-end gap-[2px]">
                  {[40, 70, 55].map((h, i) => (
                    <i
                      key={i}
                      className="flex-1 rounded-[1px] bg-warn opacity-[0.85]"
                      style={{ height: `${h}%` }}
                    />
                  ))}
                </span>
                <div>
                  <div className="text-[13px] font-semibold">{g.skill}</div>
                  <div className="mt-px font-mono text-[10.5px] text-ink-2">
                    {g.note}
                  </div>
                </div>
                <span className="ml-auto font-mono text-[18px] font-semibold text-warn">
                  {g.roles}×
                </span>
              </div>
            ))}
            <Button className="mt-[16px] w-full justify-center">
              ✎ Draft a tailored CV bullet
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Wire the RSC page**

Replace `apps/web/src/app/(app)/candidate/page.tsx` with:

```tsx
import { CandidateView } from "@/components/candidate/candidate-view";
import { getCandidate } from "@/lib/api/candidate";
import { getSkillsGap } from "@/lib/api/skills-gap";

export default function CandidatePage() {
  return <CandidateView candidate={getCandidate()} skillsGap={getSkillsGap()} />;
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pnpm test src/components/candidate/candidate-view.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 7: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/config apps/web/src/components/candidate "apps/web/src/app/(app)/candidate/page.tsx"
git commit -m "feat(web): Candidate profile view (form, live skills TagEditor, skills-gap panel) (M1b-3)"
```

---

### Task 4: Targeting (TargetingView + page) + build gate

**Files:**
- Create: `apps/web/src/components/targeting/targeting-view.tsx`
- Test: `apps/web/src/components/targeting/targeting-view.test.tsx`
- Modify: `apps/web/src/app/(app)/targeting/page.tsx`

**Interfaces:**
- Consumes: `Targeting` from `@specula/shared-types`; `TagEditor` atom; `Field` from `@/components/config/field` (Task 3); `getTargeting` from `@/lib/api/targeting` (page + test).
- Produces: `TargetingView({ targeting: Targeting })` — `"use client"`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/targeting/targeting-view.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { TargetingView } from "@/components/targeting/targeting-view";
import { getTargeting } from "@/lib/api/targeting";

afterEach(cleanup);
const t = getTargeting();

describe("TargetingView", () => {
  it("renders tag fields, seniority chips, preferences, and the invariant banner", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getByText(t.roleTitles[0])).toBeInTheDocument();
    expect(screen.getByText(t.seniority[0])).toBeInTheDocument();
    expect(screen.getByDisplayValue(t.preferences)).toBeInTheDocument();
    expect(screen.getByText(/never a rule or signal/)).toBeInTheDocument();
  });

  it("has three tag editors (role titles, must-haves, avoid)", () => {
    render(<TargetingView targeting={t} />);
    expect(screen.getAllByText("+ add")).toHaveLength(3);
  });

  it("adds a role-title tag locally (wiring)", () => {
    render(<TargetingView targeting={t} />);
    fireEvent.click(screen.getAllByText("+ add")[0]); // first TagEditor = role titles
    const input = document.activeElement as HTMLInputElement;
    fireEvent.change(input, { target: { value: "LLM Engineer" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByText("LLM Engineer")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/targeting/targeting-view.test.tsx`
Expected: FAIL — cannot resolve `@/components/targeting/targeting-view`.

- [ ] **Step 3: Implement TargetingView (from `config.jsx:140–182` + `views.css` `.field*`/`.taglist`/`.tagchip`/`.textarea` + accent banner)**

Create `apps/web/src/components/targeting/targeting-view.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { Targeting } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Field } from "@/components/config/field";

export function TargetingView({ targeting: t }: { targeting: Targeting }) {
  const [titles, setTitles] = useState(t.roleTitles);
  const [must, setMust] = useState(t.mustHaves);
  const [avoid, setAvoid] = useState(t.avoid);

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
          <TagEditor kind="syn" values={titles} onChange={setTitles} />
        </Field>
        <Field label="Seniority">
          <div className="flex flex-wrap gap-2">
            {t.seniority.map((s) => (
              <span
                key={s}
                className="rounded-[7px] border border-rule bg-panel px-3 py-[6px] text-[12.5px] text-ink"
              >
                {s}
              </span>
            ))}
          </div>
        </Field>
        <div className="grid grid-cols-2 gap-[24px]">
          <Field label="Must-haves">
            <TagEditor values={must} onChange={setMust} />
          </Field>
          <Field label="Avoid">
            <TagEditor kind="avoid" values={avoid} onChange={setAvoid} />
          </Field>
        </div>
        <Field label="Free-text preferences · fed to the model as soft signal">
          <textarea
            rows={4}
            defaultValue={t.preferences}
            className="min-h-[78px] w-full resize-y rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] leading-[1.55] text-ink focus:border-ink focus:outline-none"
          />
        </Field>
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

- [ ] **Step 4: Wire the RSC page**

Replace `apps/web/src/app/(app)/targeting/page.tsx` with:

```tsx
import { TargetingView } from "@/components/targeting/targeting-view";
import { getTargeting } from "@/lib/api/targeting";

export default function TargetingPage() {
  return <TargetingView targeting={getTargeting()} />;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/components/targeting/targeting-view.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Run all gates + build**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check && pnpm build`
Expected: all green — full Vitest suite passes, `next build` compiles (the `/profiles`, `/candidate`, `/targeting` routes now render their views; `ViewShell` is no longer used by any page and can be left as an unused component or removed — do NOT remove it in this task). If `pnpm build` fails with a TLS/cert error (`SELF_SIGNED_CERT_IN_CHAIN`), re-run as `NODE_EXTRA_CA_CERTS="$HOME/.corp-ca.pem" pnpm build` (corporate proxy; the only sanctioned workaround — do not disable TLS verification).

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/targeting "apps/web/src/app/(app)/targeting/page.tsx"
git commit -m "feat(web): Targeting view (tag fields, invariant banner, live editing) (M1b-3)"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** Task 1 → §2 data-access + §3 route refactor. Task 2 → §4 Search profiles (derived active/total + card counts, live toggle, hard rules, seeds, inert "+ New profile"). Task 3 → §5 Candidate (seed avatar, form inputs, live Skills TagEditor, read-only Projects/Experience/Education/Languages, skills-gap panel, inert "Draft CV bullet") + the shared `Field`. Task 4 → §6 Targeting (three TagEditors, seniority chips, preferences, the geography+salary invariant banner) + the build gate + §8 acceptance. Deferred items honored: live-but-not-persisted editing, inert backend-action buttons, no animations.
- **Type consistency:** `getTargeting`/`getSkillsGap` (Task 1) used verbatim by Tasks 3–4 pages/tests. `getLenses` (M1b-1) reused by Task 2 — `LensSummary` carries `active`/`scope`/`modes`/`origin`/`focus`/`seeds`/`count`/`isNew`. `TagEditor` = `{ values, onChange, kind }`, `Toggle` = `{ on, onChange }` — matched exactly. `Field` (Task 3) consumed by Task 4.
- **Derived counts** asserted against regression: Profiles 4 active / 5 total + per-card `count`/`isNew` (Task 2).
- **Live-local wiring** verified by the add/remove tests (Tasks 3–4) — the TagEditor internals are already atom-tested (M1a), so these assert the view's `useState` wiring only.
- **Seed avatar (not session):** Task 3 asserts `c.initials` ("JV") — the identity is the seed candidate, independent of who's signed in.
- **No new E2E** — auth-gated views; the unauth redirect is already covered (M0b). `pnpm build` is the integration gate (Task 4).
