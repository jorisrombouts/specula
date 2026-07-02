# M1b-1 — Jobs view + Drawer (static) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the prototype's Jobs view + detail Drawer to typed React against the M1a seed/atoms — statically (pixel-faithful, real derived data, an openable drawer), with no signature animations (M1c) and no persisting interactivity (M2).

**Architecture:** A typed `lib/api/` data-access layer wraps the M1a seed logic; the M1a `/api/*` routes are refactored to call it (DRY). The RSC `jobs/page.tsx` fetches the pool + lenses + candidate and passes them to a client `<JobsView>`, which does lens/sort **client-side** via the shared pure logic (so M1c's FLIP drops in with zero rework) and owns the drawer open/close state. Components are split by responsibility (data-access / skills / lens-bar / job-row / drawer-sections / drawer / view) so each file is focused and independently testable.

**Tech Stack:** Next.js 16 (App Router, RSC + client islands), React 19, TypeScript strict, Tailwind v4 (CSS-first, arbitrary values translating `views.css`), Vitest + @testing-library/react (jsdom), `@specula/shared-types`.

## Global Constraints

- **Next.js 16, TypeScript strict, Tailwind-native.** Rebuild each prototype component in Tailwind arbitrary-value classes translated from `prototype/specula/views.css` + `prototype/specula/specula.css`. Do **not** import prototype CSS. Match the M1a atom idiom (`apps/web/src/components/atoms/match-meter.tsx`) and theme tokens in `apps/web/src/app/globals.css` (`paper`, `panel`, `panel-2`, `card`, `ink`, `ink-2`, `ink-3`, `rule`, `rule-2`, `accent`, `accent-bg`, `accent-ink`, `warn`, `warn-bg`, `gold`; `font-display`/`font-body`/`font-mono`; `shadow-card`/`shadow-pop`). Prototype `var(--rule-2)` → Tailwind `rule-2`, etc.
- **Counts DERIVED, never hard-coded.** Every count (view-header pool/new, lens-bar "N roles · M new") comes from `filterByLens`/`deriveLensSummaries` over the pool — the real 13/7-style values, **never** the prototype's cosmetic 47/11.
- **Salary is display-only.** Shown in the row meta + insight record when present ("not stated in ad" when null); never sorts, filters, or scores.
- **Lens + sort switch client-side** (React state), **not** via the URL — the rows must persist in the DOM for M1c's FLIP.
- **Animations → M1c** (the four signature moments + rowIn/viewIn entrance stagger + reduced-motion). The drawer's plain slide-in **is** in M1b (spec §5). MatchMeter renders its final value (no `reveal`).
- **Mutations → M2.** The drawer's status/feedback/save/note controls render at full visual fidelity but are **inert** (display the seed's current state).
- **Testing = Vitest component + data-access tests** (`import { describe, it, expect, afterEach } from "vitest"`; `render/screen/fireEvent/cleanup` from `@testing-library/react`; `afterEach(cleanup)`). Views are auth-gated → **no new E2E** (the unauth redirect is already covered).
- **Sources of truth:** `jobs.jsx` (structure), `views.css`/`specula.css` (styling), spec `docs/superpowers/specs/2026-07-02-m1b-1-jobs-drawer-design.md`. All commands run from `apps/web`.

---

### Task 1: Data-access layer + `/api` route refactor (DRY)

**Files:**
- Create: `apps/web/src/lib/api/jobs.ts`, `apps/web/src/lib/api/lenses.ts`, `apps/web/src/lib/api/candidate.ts`
- Test: `apps/web/src/lib/api/jobs.test.ts`
- Modify: `apps/web/src/app/api/jobs/route.ts`, `apps/web/src/app/api/jobs/[id]/route.ts`, `apps/web/src/app/api/lenses/route.ts`, `apps/web/src/app/api/candidate/route.ts`

**Interfaces:**
- Consumes: `filterByLens`, `scoreForLens`, `deriveLensSummaries`, `sortJobs` from `@/lib/seed/logic`; `jobs`, `lenses`, `candidate` from `@/lib/seed/data`; types from `@specula/shared-types`.
- Produces (later tasks + RSC page rely on these exact signatures):
  - `getJobsPool(): Job[]` — the full raw pool (base scores intact).
  - `getJob(id: string): Job | null`
  - `getJobs(lens: string, sort: JobSort): JobsResponse` — filtered, re-scored, sorted list + derived lens summaries.
  - `getLenses(): LensSummary[]` — derived per-lens counts.
  - `getCandidate(): Candidate`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/api/jobs.test.ts`:

```tsx
import { describe, it, expect } from "vitest";
import { getJobsPool, getJob, getJobs } from "@/lib/api/jobs";
import { getLenses } from "@/lib/api/lenses";
import { getCandidate } from "@/lib/api/candidate";
import { GET as jobsRoute } from "@/app/api/jobs/route";

describe("lib/api data-access", () => {
  it("getJobsPool returns the full 13-job pool", () => {
    expect(getJobsPool()).toHaveLength(13);
  });

  it("getJob returns a job by id, or null", () => {
    expect(getJob("j1")?.id).toBe("j1");
    expect(getJob("nope")).toBeNull();
  });

  it("getJobs('all','match') returns 13 jobs sorted desc by match + derived lenses", () => {
    const res = getJobs("all", "match");
    expect(res.jobs).toHaveLength(13);
    expect(res.sort).toBe("match");
    expect(res.jobs.every((j, i) => i === 0 || res.jobs[i - 1].match >= j.match)).toBe(true);
    const all = res.lenses.find((l) => l.id === "all")!;
    expect(all.count).toBe(13); // DERIVED — not 47
    expect(all.isNew).toBe(7); // DERIVED — not 11
  });

  it("getJobs('foreign','match') filters + re-scores per lens", () => {
    const res = getJobs("foreign", "match");
    expect(res.jobs.length).toBeGreaterThan(0);
    expect(res.jobs.length).toBeLessThan(13);
  });

  it("getLenses returns 5 derived summaries", () => {
    const ls = getLenses();
    expect(ls).toHaveLength(5);
    expect(ls.find((l) => l.id === "all")!.count).toBe(13);
  });

  it("getCandidate returns the candidate profile", () => {
    expect(getCandidate().skills.length).toBeGreaterThan(0);
  });

  it("the refactored /api/jobs route still returns the JobsResponse shape", async () => {
    const res = jobsRoute(new Request("http://x/api/jobs?lens=all&sort=match"));
    const body = await res.json();
    expect(body.jobs).toHaveLength(13);
    expect(body.lenses.find((l: { id: string }) => l.id === "all").count).toBe(13);
    expect(body.sort).toBe("match");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/lib/api/jobs.test.ts`
Expected: FAIL — cannot resolve `@/lib/api/jobs` (module not found).

- [ ] **Step 3: Create the data-access layer**

Create `apps/web/src/lib/api/jobs.ts`:

```ts
import type { Job, JobSort, JobsResponse } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import {
  filterByLens,
  scoreForLens,
  deriveLensSummaries,
  sortJobs,
} from "@/lib/seed/logic";

// The full deduped pool, base-scored (lens-independent). M2: BFF → FastAPI.
export function getJobsPool(): Job[] {
  return jobs.slice();
}

export function getJob(id: string): Job | null {
  return jobs.find((j) => j.id === id) ?? null;
}

// The lens-filtered, re-scored, sorted list + derived lens summaries.
export function getJobs(lens: string, sort: JobSort): JobsResponse {
  const scored = filterByLens(jobs, lens).map((job) => {
    const s = scoreForLens(job, lens);
    return { ...job, match: s.match, factors: s.factors, redFlag: s.redFlag };
  });
  return {
    jobs: sortJobs(scored, sort),
    lenses: deriveLensSummaries(lenses, jobs),
    sort,
  };
}
```

Create `apps/web/src/lib/api/lenses.ts`:

```ts
import type { LensSummary } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";

export function getLenses(): LensSummary[] {
  return deriveLensSummaries(lenses, jobs);
}
```

Create `apps/web/src/lib/api/candidate.ts`:

```ts
import type { Candidate } from "@specula/shared-types";
import { candidate } from "@/lib/seed/data";

export function getCandidate(): Candidate {
  return candidate;
}
```

- [ ] **Step 4: Refactor the four routes to call the data-access layer**

Replace `apps/web/src/app/api/jobs/route.ts` with:

```ts
import { NextResponse } from "next/server";
import type { JobSort, JobsResponse } from "@specula/shared-types";
import { getJobs } from "@/lib/api/jobs";

export function GET(request: Request): NextResponse<JobsResponse> {
  const url = new URL(request.url);
  const lens = url.searchParams.get("lens") ?? "all";
  const sortParam = url.searchParams.get("sort");
  const sort: JobSort =
    sortParam === "deadline" || sortParam === "new" ? sortParam : "match";
  return NextResponse.json(getJobs(lens, sort));
}
```

Replace `apps/web/src/app/api/jobs/[id]/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getJob } from "@/lib/api/jobs";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const job = getJob(id);
  if (!job) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(job);
}
```

Replace `apps/web/src/app/api/lenses/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getLenses } from "@/lib/api/lenses";

export function GET(): NextResponse {
  return NextResponse.json(getLenses());
}
```

Replace `apps/web/src/app/api/candidate/route.ts` with:

```ts
import { NextResponse } from "next/server";
import { getCandidate } from "@/lib/api/candidate";

export function GET(): NextResponse {
  return NextResponse.json(getCandidate());
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/lib/api/jobs.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 6: Run the gates**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check`
Expected: all green (full suite still passes; the routes' behavior is unchanged).

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/api apps/web/src/app/api
git commit -m "refactor(web): lib/api data-access layer; /api routes call it (M1b-1)"
```

---

### Task 2: Skill matching (`candidateHas` + `splitSkills`)

**Files:**
- Create: `apps/web/src/components/jobs/skills.ts`
- Test: `apps/web/src/components/jobs/skills.test.ts`

**Interfaces:**
- Consumes: `Candidate` from `@specula/shared-types`; `getCandidate`, `getJobsPool` from `@/lib/api/*` (tests only).
- Produces:
  - `candidateHas(candidate: Candidate, skill: string): boolean`
  - `splitSkills(candidate: Candidate, required: string[]): { have: string[]; miss: string[] }`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/jobs/skills.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { candidateHas, splitSkills } from "@/components/jobs/skills";
import type { Candidate } from "@specula/shared-types";

const cand = {
  skills: ["Python", "PyTorch", "Distributed Systems"],
} as Candidate;

describe("skill matching", () => {
  it("candidateHas matches exact + substring (either direction)", () => {
    expect(candidateHas(cand, "Python")).toBe(true); // exact
    expect(candidateHas(cand, "PyTorch Lightning")).toBe(true); // target includes "pytorch"
    expect(candidateHas(cand, "Rust")).toBe(false);
  });

  it("splitSkills partitions required into have/miss covering all", () => {
    const { have, miss } = splitSkills(cand, ["Python", "Rust", "PyTorch"]);
    expect(have).toEqual(["Python", "PyTorch"]);
    expect(miss).toEqual(["Rust"]);
    expect([...have, ...miss].sort()).toEqual(["Python", "PyTorch", "Rust"].sort());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/jobs/skills.test.ts`
Expected: FAIL — cannot resolve `@/components/jobs/skills`.

- [ ] **Step 3: Implement (ported verbatim from `jobs.jsx:8–12`)**

Create `apps/web/src/components/jobs/skills.ts`:

```ts
import type { Candidate } from "@specula/shared-types";

export function candidateHas(candidate: Candidate, skill: string): boolean {
  const cs = candidate.skills.map((s) => s.toLowerCase());
  const t = skill.toLowerCase();
  return cs.some((c) => c === t || c.includes(t) || t.includes(c.split(" ")[0]));
}

export function splitSkills(
  candidate: Candidate,
  required: string[],
): { have: string[]; miss: string[] } {
  return {
    have: required.filter((s) => candidateHas(candidate, s)),
    miss: required.filter((s) => !candidateHas(candidate, s)),
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test src/components/jobs/skills.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/jobs/skills.ts apps/web/src/components/jobs/skills.test.ts
git commit -m "feat(web): candidateHas + splitSkills skill matching (M1b-1)"
```

---

### Task 3: LensBar

**Files:**
- Create: `apps/web/src/components/jobs/lens-bar.tsx`
- Test: `apps/web/src/components/jobs/lens-bar.test.tsx`

**Interfaces:**
- Consumes: `LensSummary` from `@specula/shared-types`; `getLenses` from `@/lib/api/lenses` (test).
- Produces: `LensBar({ lenses: LensSummary[]; active: string; onSelect: (id: string) => void })`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/jobs/lens-bar.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { LensBar } from "@/components/jobs/lens-bar";
import { getLenses } from "@/lib/api/lenses";

afterEach(cleanup);

describe("LensBar", () => {
  it("shows DERIVED per-lens counts (all → 13 roles · 7 new, not 47/11)", () => {
    render(<LensBar lenses={getLenses()} active="all" onSelect={() => {}} />);
    expect(screen.getByText("13 roles · 7 new")).toBeInTheDocument();
    expect(screen.queryByText(/47 roles/)).toBeNull();
  });

  it("marks the active lens", () => {
    const { container } = render(
      <LensBar lenses={getLenses()} active="all" onSelect={() => {}} />,
    );
    // active cell carries bg-ink
    expect(container.querySelector("button.bg-ink")).not.toBeNull();
  });

  it("calls onSelect with the lens id on click", () => {
    const onSelect = vi.fn();
    render(<LensBar lenses={getLenses()} active="all" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Remote").closest("button")!);
    expect(onSelect).toHaveBeenCalledWith("remote");
  });
});
```

> Note: the click test targets the lens whose `short` is "Remote" and `id` is "remote" (seed `lenses`). If the seed short differs, use `getLenses().find(l => l.id === "remote")!.short`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/jobs/lens-bar.test.tsx`
Expected: FAIL — cannot resolve `@/components/jobs/lens-bar`.

- [ ] **Step 3: Implement (from `jobs.jsx:353–364` + `views.css` `.lens-bar`/`.lens`)**

Create `apps/web/src/components/jobs/lens-bar.tsx`:

```tsx
import type { LensSummary } from "@specula/shared-types";

export function LensBar({
  lenses,
  active,
  onSelect,
}: {
  lenses: LensSummary[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="mt-[18px] flex overflow-hidden rounded-[8px] border border-rule-2 bg-card">
      {lenses.map((l) => {
        const on = l.id === active;
        return (
          <button
            key={l.id}
            onClick={() => onSelect(l.id)}
            className={`flex min-w-0 flex-1 flex-col gap-[4px] border-r border-rule px-[14px] py-[11px] text-left transition-colors last:border-r-0 ${
              on ? "bg-ink" : "hover:bg-panel"
            }`}
          >
            <span
              className={`flex items-center gap-[6px] text-[13px] font-semibold ${
                on ? "text-paper" : "text-ink"
              }`}
            >
              {l.short}
              {l.isNew > 0 && (
                <span
                  className={`h-[6px] w-[6px] rounded-full ${on ? "bg-[#7FD3A0]" : "bg-accent"}`}
                />
              )}
            </span>
            <span
              className={`font-mono text-[10px] ${on ? "text-[rgba(251,250,246,0.55)]" : "text-ink-2"}`}
            >
              {l.count} roles · {l.isNew} new
            </span>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test src/components/jobs/lens-bar.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/jobs/lens-bar.tsx apps/web/src/components/jobs/lens-bar.test.tsx
git commit -m "feat(web): LensBar with derived per-lens counts (M1b-1)"
```

---

### Task 4: JobRow

**Files:**
- Create: `apps/web/src/components/jobs/job-row.tsx`
- Test: `apps/web/src/components/jobs/job-row.test.tsx`

**Interfaces:**
- Consumes: `Job` from `@specula/shared-types`; `MatchMeter`, `OverlapBar`, `Tag` atoms; `getJobsPool` from `@/lib/api/jobs` (test).
- Produces: `JobRow({ job: Job; i: number; onOpen: (job: Job) => void })`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/jobs/job-row.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { JobRow } from "@/components/jobs/job-row";
import { getJobsPool } from "@/lib/api/jobs";

afterEach(cleanup);
const pool = getJobsPool();
const base = pool[0];

describe("JobRow", () => {
  it("renders index, title, company, deadline", () => {
    render(<JobRow job={base} i={0} onOpen={() => {}} />);
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText(base.title)).toBeInTheDocument();
    expect(screen.getByText(base.company)).toBeInTheDocument();
    expect(
      screen.getByText(`↳ closes ${base.deadlineDays}d`),
    ).toBeInTheDocument();
  });

  it("shows the NEW tag only when isNew", () => {
    render(<JobRow job={{ ...base, isNew: true }} i={0} onOpen={() => {}} />);
    expect(screen.getByText("NEW")).toBeInTheDocument();
    cleanup();
    render(<JobRow job={{ ...base, isNew: false }} i={0} onOpen={() => {}} />);
    expect(screen.queryByText("NEW")).toBeNull();
  });

  it("shows a red-flag tag when present, and hides salary when null", () => {
    render(
      <JobRow
        job={{ ...base, redFlag: "Low required-skill overlap", salary: null }}
        i={0}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText(/⚑ Low required-skill overlap/)).toBeInTheDocument();
    // salary hidden: no "€" and no "/yr"-style token from base.salary
    if (base.salary) expect(screen.queryByText(base.salary)).toBeNull();
  });

  it("calls onOpen with the job when clicked", () => {
    const onOpen = vi.fn();
    render(<JobRow job={base} i={2} onOpen={onOpen} />);
    fireEvent.click(screen.getByText(base.title));
    expect(onOpen).toHaveBeenCalledWith(base);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/jobs/job-row.test.tsx`
Expected: FAIL — cannot resolve `@/components/jobs/job-row`.

- [ ] **Step 3: Implement (from `jobs.jsx:14–56` + `views.css` `.jrow`/`.jline*`)**

Create `apps/web/src/components/jobs/job-row.tsx`. **Note:** the prototype `.jrow` has a `rowIn` entrance animation and a `::before` hover panel — the entrance is **deferred to M1c** (omit it; the row renders statically visible); the hover panel is kept via `before:` utilities.

```tsx
import type { Job } from "@specula/shared-types";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Tag } from "@/components/atoms/tag";

export function JobRow({
  job,
  i,
  onOpen,
}: {
  job: Job;
  i: number;
  onOpen: (job: Job) => void;
}) {
  return (
    <article
      data-fid={job.id}
      onClick={() => onOpen(job)}
      className="relative isolate grid cursor-pointer grid-cols-[30px_1fr_248px] items-start gap-[18px] border-b border-rule py-[var(--row-py)] before:absolute before:inset-y-0 before:-inset-x-[14px] before:-z-10 before:rounded-[8px] before:bg-panel before:opacity-0 before:transition-opacity hover:before:opacity-100"
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
              <span className="font-mono text-[11px] text-ink">{job.salary}</span>
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
      <MatchMeter job={job} mstyle="bars" />
    </article>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test src/components/jobs/job-row.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/jobs/job-row.tsx apps/web/src/components/jobs/job-row.test.tsx
git commit -m "feat(web): JobRow (static, no entrance animation) (M1b-1)"
```

---

### Task 5: Drawer sections (`Section`, `InsightRecord`, `SkillsSplit`, `Lifecycle`, `Feedback`)

**Files:**
- Create: `apps/web/src/components/jobs/drawer-sections.tsx`
- Test: `apps/web/src/components/jobs/drawer-sections.test.tsx`

**Interfaces:**
- Consumes: `Job`, `Candidate`, `JobStatus` from `@specula/shared-types`; `splitSkills` from `@/components/jobs/skills`.
- Produces:
  - `Section({ head?: string; note?: string; children: React.ReactNode })`
  - `InsightRecord({ job: Job })`
  - `SkillsSplit({ job: Job; candidate: Candidate })`
  - `Lifecycle({ status: JobStatus | null; note: string })` — **display-only (inert)**
  - `Feedback()` — **display-only (inert)**

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/jobs/drawer-sections.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import {
  InsightRecord,
  SkillsSplit,
  Lifecycle,
  Feedback,
} from "@/components/jobs/drawer-sections";
import { getJobsPool } from "@/lib/api/jobs";
import type { Candidate } from "@specula/shared-types";

afterEach(cleanup);
const base = getJobsPool()[0];

describe("drawer sections", () => {
  it("InsightRecord marks low-confidence extraction as 'surfaced, not trusted' (<75)", () => {
    render(<InsightRecord job={{ ...base, confidence: 60 }} />);
    expect(screen.getByText(/60% confidence — surfaced, not trusted/)).toBeInTheDocument();
  });

  it("InsightRecord shows plain confidence when >= 75", () => {
    render(<InsightRecord job={{ ...base, confidence: 90 }} />);
    expect(screen.getByText("90% confidence")).toBeInTheDocument();
    expect(screen.queryByText(/surfaced, not trusted/)).toBeNull();
  });

  it("InsightRecord shows 'not stated in ad' when salary is null", () => {
    render(<InsightRecord job={{ ...base, salary: null }} />);
    expect(screen.getByText("not stated in ad")).toBeInTheDocument();
  });

  it("SkillsSplit renders have (✓) and miss (+) chips", () => {
    const cand = { skills: ["Python"] } as Candidate;
    render(<SkillsSplit job={{ ...base, stack: ["Python", "Rust"] }} candidate={cand} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Rust")).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument();
    expect(screen.getByText("+")).toBeInTheDocument();
  });

  it("Lifecycle marks the current status step", () => {
    render(<Lifecycle status="Applied" note="" />);
    expect(screen.getByText("Applied")).toBeInTheDocument();
    // Saved (done, n<idx) + Applied (active, n===idx) each carry a check
    expect(screen.getAllByText("✓").length).toBe(2);
  });

  it("Feedback renders the two default (inert) controls", () => {
    render(<Feedback />);
    expect(screen.getByText("↑ Good match")).toBeInTheDocument();
    expect(screen.getByText("↓ Not for me")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/jobs/drawer-sections.test.tsx`
Expected: FAIL — cannot resolve `@/components/jobs/drawer-sections`.

- [ ] **Step 3: Implement (from `jobs.jsx:58–127` + `views.css` `.dr-sec*`/`.kv`/`.skillgap`/`.sg`/`.life*`/`.fb*`)**

Create `apps/web/src/components/jobs/drawer-sections.tsx`. **Note:** `Lifecycle` and `Feedback` are **inert** in M1b (no `onSet`/`onLike` handlers; the textarea is `readOnly`) — mutations are M2. The lifecycle steps render as non-interactive `<div>`s.

```tsx
import { Fragment } from "react";
import type { Job, Candidate, JobStatus } from "@specula/shared-types";
import { splitSkills } from "@/components/jobs/skills";

const LIFECYCLE: JobStatus[] = ["Saved", "Applied", "Interviewing", "Offer"];

export function Section({
  head,
  note,
  children,
}: {
  head?: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-[26px]">
      {head && (
        <div className="mb-[14px] flex justify-between border-b border-rule pb-[10px] font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
          <span>{head}</span>
          {note && <span>{note}</span>}
        </div>
      )}
      {children}
    </div>
  );
}

export function InsightRecord({ job }: { job: Job }) {
  const lowConf = job.confidence < 75;
  const rows: [string, string][] = [
    ["role family", job.title.split("—")[0].trim()],
    ["seniority", job.seniority],
    ["experience", "3–6 yrs (inferred)"],
    ["education", job.edu],
    ["work mode", job.mode],
    ["location", `${job.flag} ${job.city}`],
    ["geo", job.geo],
    ["visa", job.visa],
    ["languages", job.langs.join(", ")],
    ["salary", job.salary || "not stated in ad"],
    ["contract", job.contract],
    ["deadline", `in ${job.deadlineDays} days`],
    ["posted", job.posted],
    ["still open", job.stillOpen ? "likely open" : "likely closed"],
  ];
  return (
    <dl className="grid grid-cols-[130px_1fr] gap-x-[14px] gap-y-[7px] text-[13px]">
      {rows.map(([k, v]) => (
        <Fragment key={k}>
          <dt className="pt-px font-mono text-[11px] text-ink-2">{k}</dt>
          <dd className="m-0 text-ink">{v}</dd>
        </Fragment>
      ))}
      <dt className="pt-px font-mono text-[11px] text-ink-2">extraction</dt>
      <dd className={`m-0 ${lowConf ? "text-warn" : "text-ink"}`}>
        {job.confidence}% confidence
        {lowConf ? " — surfaced, not trusted" : ""}
      </dd>
    </dl>
  );
}

export function SkillsSplit({
  job,
  candidate,
}: {
  job: Job;
  candidate: Candidate;
}) {
  const { have, miss } = splitSkills(candidate, job.stack);
  return (
    <>
      <div className="flex flex-wrap gap-[7px]">
        {have.map((s) => (
          <span
            key={s}
            className="inline-flex items-center gap-[6px] rounded-[6px] bg-accent-bg px-[10px] py-[4px] text-[12px] text-accent-ink"
          >
            <span className="font-mono text-[11px]">✓</span>
            {s}
          </span>
        ))}
        {miss.map((s) => (
          <span
            key={s}
            className="inline-flex items-center gap-[6px] rounded-[6px] border border-dashed border-warn bg-warn-bg px-[10px] py-[4px] text-[12px] text-warn"
          >
            <span className="font-mono text-[11px]">+</span>
            {s}
          </span>
        ))}
      </div>
      {miss.length > 0 && (
        <p className="mt-[12px] text-[12.5px] leading-[1.5] text-ink-2">
          Gaps highlighted in amber feed your <b>skills-gap</b> view — add them
          to your profile or use them to tailor a CV bullet.
        </p>
      )}
    </>
  );
}

// Display-only in M1b (inert). M2 wires status changes + note persistence.
export function Lifecycle({
  status,
  note,
}: {
  status: JobStatus | null;
  note: string;
}) {
  const idx = status ? LIFECYCLE.indexOf(status) : -1;
  return (
    <div>
      <div className="my-[4px] flex items-center">
        {LIFECYCLE.map((s, n) => {
          const done = n < idx;
          const active = n === idx;
          return (
            <div
              key={s}
              className="relative flex flex-1 flex-col items-center gap-[7px]"
            >
              {n > 0 && (
                <span
                  className={`absolute left-[-50%] top-[9px] -z-10 h-[2px] w-full ${done ? "bg-accent" : "bg-rule"}`}
                />
              )}
              <span
                className={`z-[1] flex h-[20px] w-[20px] items-center justify-center rounded-full border-2 text-[10px] ${
                  done
                    ? "border-accent bg-accent text-white"
                    : active
                      ? "border-ink bg-ink text-white shadow-[0_0_0_4px_var(--color-panel-2)]"
                      : "border-rule-2 bg-card text-transparent"
                }`}
              >
                {n <= idx ? "✓" : ""}
              </span>
              <span
                className={`font-mono text-[9.5px] tracking-[0.02em] ${n <= idx ? "text-ink" : "text-ink-2"}`}
              >
                {s}
              </span>
            </div>
          );
        })}
      </div>
      <textarea
        className="mt-[14px] w-full resize-none rounded-[8px] border border-rule-2 bg-card px-[12px] py-[10px] font-body text-[13px] text-ink focus:border-ink focus:outline-none"
        rows={2}
        placeholder="Add a note (e.g. referred by Anna, recruiter call Tue)…"
        defaultValue={note}
        readOnly
      />
    </div>
  );
}

// Display-only in M1b (inert). M2 wires like/dismiss.
export function Feedback() {
  return (
    <div className="flex gap-[10px]">
      <div className="flex flex-1 items-center justify-center gap-[8px] rounded-[9px] border border-rule-2 bg-card py-[11px] text-[13px] font-medium text-ink">
        ↑ Good match
      </div>
      <div className="flex flex-1 items-center justify-center gap-[8px] rounded-[9px] border border-rule-2 bg-card py-[11px] text-[13px] font-medium text-ink">
        ↓ Not for me
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test src/components/jobs/drawer-sections.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/jobs/drawer-sections.tsx apps/web/src/components/jobs/drawer-sections.test.tsx
git commit -m "feat(web): drawer sections (insight record, skills, lifecycle, feedback — inert) (M1b-1)"
```

---

### Task 6: JobDrawer

**Files:**
- Create: `apps/web/src/components/jobs/job-drawer.tsx`
- Test: `apps/web/src/components/jobs/job-drawer.test.tsx`
- Modify: `apps/web/src/app/globals.css` (add the `drawerIn` keyframe)

**Interfaces:**
- Consumes: `Job`, `Candidate` from `@specula/shared-types`; `MatchMeter`, `OverlapBar`, `Tag`, `Button` atoms; `Section`, `InsightRecord`, `SkillsSplit`, `Lifecycle`, `Feedback` from `./drawer-sections`.
- Produces: `JobDrawer({ job: Job; candidate: Candidate; onClose: () => void })`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/jobs/job-drawer.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { JobDrawer } from "@/components/jobs/job-drawer";
import { getJobsPool } from "@/lib/api/jobs";
import { getCandidate } from "@/lib/api/candidate";

afterEach(cleanup);
const job = getJobsPool()[0];
const candidate = getCandidate();

describe("JobDrawer", () => {
  it("renders the title + all section heads", () => {
    render(<JobDrawer job={job} candidate={candidate} onClose={() => {}} />);
    expect(screen.getByRole("heading", { name: job.title })).toBeInTheDocument();
    for (const head of [
      "summary",
      "skills · required vs your profile",
      "insight record",
      "responsibilities",
      "application status",
      "feedback",
    ]) {
      expect(screen.getByText(head)).toBeInTheDocument();
    }
    expect(screen.getByText("↗ Open posting")).toBeInTheDocument();
    expect(screen.getByText("★ Save")).toBeInTheDocument();
  });

  it("closes on the ✕ button and on Escape", () => {
    const onClose = vi.fn();
    render(<JobDrawer job={job} candidate={candidate} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/jobs/job-drawer.test.tsx`
Expected: FAIL — cannot resolve `@/components/jobs/job-drawer`.

- [ ] **Step 3: Add the `drawerIn` keyframe**

In `apps/web/src/app/globals.css`, append after the `syncPulse` keyframes block (end of file):

```css
/* Drawer plain slide-in (M1b; the row→drawer morph is M1c) */
@keyframes drawerIn {
  from {
    transform: translateX(100%);
  }
  to {
    transform: none;
  }
}
```

- [ ] **Step 4: Implement (from `jobs.jsx:129–268` + `views.css` `.drawer`/`.scrim`/`.dr-*`)**

Create `apps/web/src/components/jobs/job-drawer.tsx`. **Note:** M1b renders the **plain slide-in** only (no `morphFrom`, no MatchMeter `reveal`, no close-choreography — those are M1c). Close via ✕ / scrim / Escape.

```tsx
"use client";

import { useEffect } from "react";
import type { Job, Candidate } from "@specula/shared-types";
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
}: {
  job: Job;
  candidate: Candidate;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-[rgba(33,30,24,0.28)] backdrop-blur-[2px]"
      />
      <aside
        role="dialog"
        aria-modal="true"
        className="fixed inset-y-0 right-0 z-[41] w-[560px] max-w-[94vw] overflow-y-auto border-l border-rule-2 bg-paper shadow-pop [animation:drawerIn_0.42s_cubic-bezier(0.3,0.9,0.3,1)]"
      >
        <div className="sticky top-0 z-[2] border-b border-rule bg-paper px-[28px] pt-[22px] pb-[18px]">
          <button
            onClick={onClose}
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
          <h2 className="m-0 mr-[56px] mb-[8px] font-display text-[25px] font-semibold leading-[1.12] tracking-[-0.01em]">
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
              <MatchMeter job={job} mstyle="bars" />
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

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/components/jobs/job-drawer.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/jobs/job-drawer.tsx apps/web/src/components/jobs/job-drawer.test.tsx apps/web/src/app/globals.css
git commit -m "feat(web): JobDrawer (static slide-in, all sections) (M1b-1)"
```

---

### Task 7: JobsView + Jobs page wiring

**Files:**
- Create: `apps/web/src/components/jobs/jobs-view.tsx`
- Test: `apps/web/src/components/jobs/jobs-view.test.tsx`
- Modify: `apps/web/src/app/(app)/jobs/page.tsx`

**Interfaces:**
- Consumes: `Job`, `JobSort`, `LensSummary`, `Candidate` from `@specula/shared-types`; `filterByLens`, `scoreForLens`, `sortJobs` from `@/lib/seed/logic`; `LensBar`, `JobRow`, `JobDrawer`; `getJobsPool`, `getLenses`, `getCandidate` from `@/lib/api/*` (page).
- Produces: `JobsView({ pool: Job[]; lenses: LensSummary[]; candidate: Candidate })`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/jobs/jobs-view.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { JobsView } from "@/components/jobs/jobs-view";
import { getJobsPool } from "@/lib/api/jobs";
import { getLenses } from "@/lib/api/lenses";
import { getCandidate } from "@/lib/api/candidate";

afterEach(cleanup);
const props = {
  pool: getJobsPool(),
  lenses: getLenses(),
  candidate: getCandidate(),
};

describe("JobsView", () => {
  it("renders DERIVED header counts (13 in pool · 7 new)", () => {
    // <header> nested in <section> is NOT a `banner` landmark — query the
    // element directly. The header prose contains no digits, so the only
    // "13"/"7" come from the derived pool/new counts.
    const { container } = render(<JobsView {...props} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("13");
    expect(header).toHaveTextContent("in pool");
    expect(header).toHaveTextContent("7");
    expect(header).toHaveTextContent("new");
  });

  it("renders all 13 rows in the default (all) lens", () => {
    const { container } = render(<JobsView {...props} />);
    expect(container.querySelectorAll("article[data-fid]")).toHaveLength(13);
  });

  it("shows the deadline banner (some role closes within 7 days)", () => {
    render(<JobsView {...props} />);
    expect(screen.getByText(/close within 7 days/)).toBeInTheDocument();
  });

  it("switching to a non-all lens shows the re-scored toolbar note", () => {
    render(<JobsView {...props} />);
    expect(screen.queryByText(/match re-scored for this lens/)).toBeNull();
    // "Remote" also appears in job-mode spans + the toolbar, so scope to the
    // lens buttons (the only <button>s until the drawer opens).
    const remoteBtn = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("Remote"))!;
    fireEvent.click(remoteBtn);
    expect(screen.getByText(/match re-scored for this lens/)).toBeInTheDocument();
  });

  it("opens the drawer for a clicked row and closes it on Escape", () => {
    render(<JobsView {...props} />);
    const firstRow = document.querySelector("article[data-fid]") as HTMLElement;
    const title = within(firstRow).getByRole("heading").textContent!;
    fireEvent.click(firstRow);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: title, level: 2 })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test src/components/jobs/jobs-view.test.tsx`
Expected: FAIL — cannot resolve `@/components/jobs/jobs-view`.

- [ ] **Step 3: Implement JobsView (from `jobs.jsx:270–407` + `specula.css` `.vhead*` + `views.css` `.toolbar`/`.colhead`)**

Create `apps/web/src/components/jobs/jobs-view.tsx`. **Note:** lens/sort are **client state** (not URL); the `viewIn`/`rowIn` entrance animations are omitted (M1c). Counts come from the derived `LensSummary` (`pool.length` / `pool.filter(isNew)` for the header).

```tsx
"use client";

import { useState } from "react";
import type {
  Job,
  JobSort,
  LensSummary,
  Candidate,
} from "@specula/shared-types";
import { filterByLens, scoreForLens, sortJobs } from "@/lib/seed/logic";
import { LensBar } from "@/components/jobs/lens-bar";
import { JobRow } from "@/components/jobs/job-row";
import { JobDrawer } from "@/components/jobs/job-drawer";

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

  const list = sortJobs(
    filterByLens(pool, lens).map((j) => ({ ...j, ...scoreForLens(j, lens) })),
    sort,
  );
  const activeLens = lenses.find((l) => l.id === lens) ?? lenses[0];
  const closingSoon = list.filter(
    (j) => j.deadlineDays <= 7 && j.status !== "Applied",
  ).length;
  const newCount = pool.filter((j) => j.isNew).length;

  return (
    <section
      data-screen-label="jobs"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
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

      <div className="relative">
        {list.length === 0 && (
          <div className="px-[20px] py-[80px] text-center text-ink-2">
            <div className="mb-[14px] text-[34px] opacity-40">⬚</div>
            No roles in this lens yet. Discovery runs weekly — or trigger a
            refresh.
          </div>
        )}
        {list.map((j, i) => (
          <JobRow key={j.id} job={j} i={i} onOpen={setSelected} />
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

- [ ] **Step 4: Wire the RSC page**

Replace `apps/web/src/app/(app)/jobs/page.tsx` with:

```tsx
import { JobsView } from "@/components/jobs/jobs-view";
import { getJobsPool } from "@/lib/api/jobs";
import { getLenses } from "@/lib/api/lenses";
import { getCandidate } from "@/lib/api/candidate";

export default function JobsPage() {
  return (
    <JobsView
      pool={getJobsPool()}
      lenses={getLenses()}
      candidate={getCandidate()}
    />
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test src/components/jobs/jobs-view.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 6: Run all gates + build**

Run: `pnpm test && pnpm lint && pnpm typecheck && pnpm format:check && pnpm build`
Expected: all green — full Vitest suite passes, `next build` compiles (the `(app)/jobs` route renders the RSC page, `ViewShell` is still used by the other placeholder pages).

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/jobs/jobs-view.tsx apps/web/src/components/jobs/jobs-view.test.tsx "apps/web/src/app/(app)/jobs/page.tsx"
git commit -m "feat(web): JobsView + RSC Jobs page (client lens/sort, static drawer) (M1b-1)"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** Task 1 → §2 data-access + §3 route refactor. Task 2 → §6 skills. Task 3 → §4 lens bar (derived counts). Task 4 → §4.1 JobRow. Task 5 → §5 drawer sections 2–7 (InsightRecord/Skills/Lifecycle/Feedback) + confidence<75. Task 6 → §5 drawer shell + section 1 (Match) + slide-in + close. Task 7 → §4 view header/toolbar/banner/colhead/list/empty + client lens/sort + drawer wiring + acceptance §8. Deferred items (animations→M1c, mutations→M2) are honored: no FLIP/morph/reveal/entrance; inert controls.
- **Type consistency:** the data-access signatures in Task 1's Interfaces are used verbatim by Task 7's page and the test fixtures throughout. `Job`/`Candidate`/`LensSummary`/`JobSort` match `@specula/shared-types`. `scoreForLens` returns `{ match, factors, redFlag? }` and is spread into `Job` in both `getJobs` (Task 1) and `JobsView` (Task 7) exactly as the M1a `/api/jobs` route did.
- **Derived counts** are asserted against regression in Tasks 1, 3, 7 (13/7, never 47/11).
- **If a test's seed assumption is off** (e.g. `getJobsPool()[0]` is already `isNew`, or the "Remote" lens `short` differs): the tests override the field explicitly (`{ ...base, isNew: true }`) or read the value from `getLenses()`. The only seed-dependent integration assertions are the DERIVED totals (13 jobs, 7 new, 5 lenses), which are fixed by the M1a seed.
- **No new E2E** — auth-gated views; the unauth redirect is already covered (M0b).
