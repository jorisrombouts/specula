# Specula M1a — Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build M1's foundation — convert the repo to a pnpm workspace with a `@specula/shared-types` package, port the prototype's seed data + lens logic into typed TS, expose it through stubbed GET API routes (server-derived counts, lens-aware scoring), and build the shared atoms (MatchMeter, OverlapBar, useCountUp, chips/tags/buttons/toggle, TagEditor) + a `/preview` gallery.

**Architecture:** `@specula/shared-types` is a **type-only, source-export** internal package (no build step; consumed via `exports: "./src/index.ts"` + a workspace symlink). The seed data + ported `filterByLens`/`scoreForLens` logic live in `apps/web/src/lib/seed`. Stub Next route handlers under `apps/web/src/app/api/*` serve typed seed data with counts derived server-side. Atoms are Tailwind-native rebuilds of the prototype's `ui.jsx` components (matching `specula.css`/`views.css` values), pure and prop-driven.

**Tech Stack:** pnpm workspace · TypeScript strict · Next.js 16 (App Router route handlers) · React 19 · Tailwind v4 · Vitest.

## Global Constraints

Apply to **every** task. Sources: `docs/superpowers/specs/2026-07-01-m1a-foundations-design.md`, prototype `prototype/specula/{data,ui}.jsx` + `{specula,views}.css`, production spec §4/§6/§8, `CLAUDE.md`.

- **Working dir:** repo root `/Users/jorisrombouts/Projects/Personal/specula`; branch **main** (direct-on-main). The JS workspace is `apps/web` + `packages/*` — **`apps/api` is NOT in the workspace** (uv Python project, untouched).
- **Port data & markup verbatim from the in-repo prototype.** Seed values come from `prototype/specula/data.jsx`; atom structure/logic from `prototype/specula/ui.jsx`; atom styling values from `prototype/specula/specula.css` + `views.css`. Do not invent data or restyle — match the prototype. (The implementer reads those files directly; they are the source of truth.)
- **Counts are DERIVED, never hard-coded** (invariant). Lens `count`/`isNew` are computed from `filterByLens` over the 13-job seed — **not** read from the prototype's cosmetic `lens.count`/`isNew` (47/11/…). The derived counts (e.g. All = 13, isNew = 7) intentionally differ from the prototype's numbers; do NOT "correct" them back.
- **Salary never ranks/filters** — `salary: string | null` is display-only; absent from all sort/filter/score logic.
- **Scores: numbers computed, prose generated** — `match`/`factors` are numeric; `rationale`/`summary` are prose; never derive one from the other.
- **Styling = Tailwind-native** (the M0a decision): rebuild atoms with Tailwind utilities + the M0a `@theme` tokens (`bg-paper`, `text-ink`, `text-warn`, `bg-accent`, `bg-panel-2`, `font-mono`, `font-display`, etc.); do NOT import the prototype CSS. Match the prototype's exact pixel values via arbitrary-value utilities.
- **shared-types is type-only** — pure `interface`/`type` exports, no runtime code (the seed/logic live in `apps/web`). `apps/web` imports it via `import type`.
- Gates stay green: `just lint/typecheck/test`, `pnpm build`, `pre-commit run --all-files`; CI (api + web) green. Vitest scope stays `src/**/*.test.{ts,tsx}`; Playwright `e2e/**`.
- Pre-commit hooks installed; web commits run `pnpm lint && pnpm format:check`. Keep new files clean.

---

## File Structure

```
pnpm-workspace.yaml                        # CREATE (T1)
package.json                               # CREATE (T1) root, private
packages/shared-types/
  package.json                             # CREATE (T1)
  tsconfig.json                            # CREATE (T1)
  src/index.ts                             # CREATE (T1 skeleton → T2 full)
apps/web/
  package.json                             # MODIFY (T1) add @specula/shared-types
  next.config.ts                           # MODIFY (T1) transpilePackages
  pnpm-lock.yaml                           # DELETE (T1) → root pnpm-lock.yaml
  src/lib/seed/
    data.ts                                # CREATE (T2) ported seed, typed
    logic.ts                               # CREATE (T2) filterByLens/scoreForLens/derive/sort
    logic.test.ts                          # CREATE (T2)
  src/app/api/
    jobs/route.ts                          # CREATE (T3)
    jobs/[id]/route.ts                     # CREATE (T3)
    lenses/route.ts                        # CREATE (T3)
    companies/route.ts                     # CREATE (T3)
    approvals/route.ts                     # CREATE (T3)
    insights/route.ts                      # CREATE (T3)
    candidate/route.ts                     # CREATE (T3)
    targeting/route.ts                     # CREATE (T3)
    jobs/route.test.ts                     # CREATE (T3)
  src/lib/use-count-up.ts                  # CREATE (T4)
  src/lib/use-count-up.test.ts             # CREATE (T4)
  src/components/atoms/
    match-meter.tsx  match-meter.test.tsx  # CREATE (T4)
    overlap-bar.tsx  overlap-bar.test.tsx  # CREATE (T4)
    chip.tsx  tag.tsx  button.tsx  toggle.tsx  # CREATE (T5)
    tag-editor.tsx   tag-editor.test.tsx   # CREATE (T5)
  src/app/preview/page.tsx                 # CREATE (T5)
.github/workflows/ci.yml                   # MODIFY (T1) cache-dependency-path → root lock
justfile                                   # MODIFY (T1) setup installs at root
```

---

### Task 1: pnpm workspace + `@specula/shared-types` skeleton

**Files:**
- Create: `pnpm-workspace.yaml`, `package.json` (root), `packages/shared-types/{package.json,tsconfig.json,src/index.ts}`
- Modify: `apps/web/package.json`, `apps/web/next.config.ts`, `.github/workflows/ci.yml`, `justfile`
- Delete: `apps/web/pnpm-lock.yaml` (→ root `pnpm-lock.yaml`)

**Interfaces:**
- Produces: the workspace; `@specula/shared-types` resolvable from `apps/web` via `import type`. Skeleton exports one type (`Mode`) — Task 2 fills the rest.

- [ ] **Step 1: Create the workspace manifests**

`pnpm-workspace.yaml`:
```yaml
packages:
  - "apps/web"
  - "packages/*"
```
`package.json` (repo root):
```json
{
  "name": "specula",
  "version": "0.0.0",
  "private": true,
  "packageManager": "pnpm@9.15.4"
}
```

- [ ] **Step 2: Create the shared-types package (skeleton)**

`packages/shared-types/package.json`:
```json
{
  "name": "@specula/shared-types",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "exports": {
    ".": "./src/index.ts"
  },
  "scripts": {
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "typescript": "^5"
  }
}
```
`packages/shared-types/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "esnext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "verbatimModuleSyntax": true
  },
  "include": ["src/**/*.ts"]
}
```
`packages/shared-types/src/index.ts` (skeleton — one type to prove resolution):
```ts
export type Mode = "Remote" | "Hybrid" | "On-site";
```

- [ ] **Step 3: Wire `apps/web` to the package**

In `apps/web/package.json`, add to `"dependencies"` (keep the rest):
```json
    "@specula/shared-types": "workspace:*"
```
In `apps/web/next.config.ts`, add `transpilePackages: ["@specula/shared-types"]` to the `nextConfig` object (read the file; insert the key into the exported config object). E.g. if it's `const nextConfig: NextConfig = {};`, make it `const nextConfig: NextConfig = { transpilePackages: ["@specula/shared-types"] };`.

- [ ] **Step 4: Install at root, relocate the lockfile**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
rm -f apps/web/pnpm-lock.yaml
pnpm install
```
Expected: a **root** `pnpm-lock.yaml` is created; `apps/web/node_modules/@specula/shared-types` is a symlink into `packages/shared-types`. (`pnpm install` from root installs the whole workspace.)

- [ ] **Step 5: Prove resolution — a web file imports the type**

Temporarily verify by type-checking a use. Create `apps/web/src/lib/types-smoke.ts`:
```ts
import type { Mode } from "@specula/shared-types";

export const REMOTE: Mode = "Remote";
```
Then:
```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm typecheck
```
Expected: PASS (the workspace package resolves; `REMOTE` is typed). If resolution fails, confirm `transpilePackages` + the package `exports` + the `workspace:*` dep. Then delete the smoke file:
```bash
rm apps/web/src/lib/types-smoke.ts
```

- [ ] **Step 6: Update CI — cache the root lockfile**

In `.github/workflows/ci.yml`, in the `web` job's `actions/setup-node` step, change:
```yaml
          cache-dependency-path: apps/web/pnpm-lock.yaml
```
to:
```yaml
          cache-dependency-path: pnpm-lock.yaml
```
(The job keeps `defaults.run.working-directory: apps/web`; `pnpm install --frozen-lockfile` run from there still installs the whole workspace against the root lockfile. The api job is unchanged.)

- [ ] **Step 7: Update the justfile `setup` to install at the workspace root**

In `justfile`, change the `setup` recipe's web install line from `cd apps/web && pnpm install` to a root install. New `setup`:
```just
# Install all deps and git hooks
setup:
    cd apps/api && uv sync
    pnpm install
    pre-commit install
```
(`dev-web`, `lint`, `typecheck`, `test` still `cd apps/web && …` — they resolve the workspace package via the symlink; no build step needed since shared-types is type-only.)

- [ ] **Step 8: Verify gates + build**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
just lint && just typecheck && just test
cd apps/web && pnpm build
cd /Users/jorisrombouts/Projects/Personal/specula && pre-commit run --all-files
```
Expected: all green. `pnpm build` succeeds (Next resolves the workspace package). `pre-commit` clean (the new root `package.json`/`pnpm-workspace.yaml` pass check-yaml/eof).

- [ ] **Step 9: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add -A
git commit -m "chore: convert to pnpm workspace with @specula/shared-types package"
```
(`git add -A` here picks up the moved lockfile + new root files. Confirm `git status` shows no stray files — the `.superpowers/` scratch is gitignored.)

---

### Task 2: shared-types domain types + ported seed + lens logic

**Files:**
- Modify: `packages/shared-types/src/index.ts` (full types)
- Create: `apps/web/src/lib/seed/data.ts`, `apps/web/src/lib/seed/logic.ts`, `apps/web/src/lib/seed/logic.test.ts`

**Interfaces:**
- Consumes: nothing from T1 beyond the package.
- Produces (from `@specula/shared-types`): `Mode`, `JobStatus`, `JobSort`, `Job`, `Lens`, `LensSummary`, `Candidate`, `Targeting`, `Company`, `Approval`, `Insights` (+ `SkillDemand`, `Trend`, `TrendSeries`, `SeniorityMix`, `ModeMix`, `SalaryBand`, `ActiveCompany`), `SkillsGap`, `JobsResponse`.
- Produces (from `@/lib/seed/data`): `candidate`, `targeting`, `lenses`, `jobs`, `companies`, `approvals`, `insights`, `skillsGap` (typed constants).
- Produces (from `@/lib/seed/logic`): `filterByLens(jobs, lensId)`, `locForLens(job, lensId)`, `scoreForLens(job, lensId)`, `deriveLensSummaries(lenses, jobs)`, `sortJobs(jobs, sort)`.

- [ ] **Step 1: Author the full domain types**

Replace `packages/shared-types/src/index.ts` with types mirroring `prototype/specula/data.jsx` **exactly** (field names/shapes). Read `data.jsx` for the precise shapes; the types are:
```ts
export type Mode = "Remote" | "Hybrid" | "On-site";
export type JobStatus = "Saved" | "Applied" | "Interviewing" | "Offer" | "Dismissed";
export type JobSort = "match" | "deadline" | "new";

export interface Factors { role: number; skill: number; loc: number }

export interface Job {
  id: string; company: string; logo: string; title: string;
  city: string; country: string; hq: string; mode: Mode; flag: string;
  match: number; factors: Factors; overlap: [number, number];
  seniority: string; edu: string; deadlineDays: number; salary: string | null;
  posted: string; status: JobStatus | null; isNew: boolean; stillOpen: boolean;
  originVerified: boolean; hqConf: number; redFlag?: string;
  stack: string[]; niceToHave: string[]; visa: string; langs: string[];
  contract: string; geo: string; confidence: number; dismissReason?: string;
  responsibilities: string[]; summary: string; rationale: string;
}

export interface Lens {
  id: string; name: string; short: string; active: boolean;
  scope: string; modes: Mode[]; origin: string; focus: string; seeds: string[];
}
export interface LensSummary extends Lens { count: number; isNew: number }

export interface Candidate {
  name: string; initials: string; title: string; location: string;
  workMode: string; visa: string; years: number; education: string;
  languages: string[]; skills: string[];
  projects: { name: string; note: string }[];
  experience: { role: string; org: string; period: string }[];
}
export interface Targeting {
  roleTitles: string[]; seniority: string[]; mustHaves: string[];
  avoid: string[]; preferences: string;
}
export interface Company {
  name: string; logo: string; domain: string; ats: string; hq: string;
  flag: string; conf: number; open: number; comp: string; added: string;
  unverified?: boolean;
}
export interface Approval {
  id: string; name: string; logo: string; domain: string; ats: string;
  hq: string; flag: string; query: string; why: string; roles: number;
  unverified?: boolean;
}
export interface SkillDemand { skill: string; pct: number; delta: number; up: boolean; gap?: boolean }
export interface TrendSeries { name: string; color: string; data: number[] }
export interface Trend { weeks: string[]; series: TrendSeries[] }
export interface SeniorityMix { k: string; v: number }
export interface ModeMix { k: string; v: number; color: string }
export interface SalaryBand { band: string; lo: number; hi: number }
export interface ActiveCompany { name: string; n: number }
export interface Insights {
  period: string; totalAnalysed: number; lowConfExcluded: number;
  skillDemand: SkillDemand[]; trend: Trend;
  seniorityMix: SeniorityMix[]; modeMix: ModeMix[];
  salary: SalaryBand[]; activeCompanies: ActiveCompany[];
}
export interface SkillsGap { skill: string; roles: number; note: string }

export interface JobsResponse { jobs: Job[]; lenses: LensSummary[]; sort: JobSort }
```

- [ ] **Step 2: Port the seed data (verbatim, typed)**

Create `apps/web/src/lib/seed/data.ts`. **Port the data objects from `prototype/specula/data.jsx` verbatim** — `SPECULA.candidate`, `.targeting`, `.lenses`, `.jobs`, `.companies`, `.approvals`, `.insights`, `.skillsGap` — into typed exported constants. Drop the prototype's `count`/`isNew` fields on lenses (they're derived — omit them; `Lens` has no such fields). Shape:
```ts
import type {
  Candidate, Targeting, Lens, Job, Company, Approval, Insights, SkillsGap,
} from "@specula/shared-types";

export const candidate: Candidate = { /* …verbatim from data.jsx SPECULA.candidate… */ };
export const targeting: Targeting = { /* …verbatim… */ };
export const lenses: Lens[] = [ /* …the 5 lenses WITHOUT count/isNew… */ ];
export const jobs: Job[] = [ /* …the 13 jobs verbatim… */ ];
export const companies: Company[] = [ /* …the 10 companies verbatim… */ ];
export const approvals: Approval[] = [ /* …the 6 approvals verbatim… */ ];
export const insights: Insights = { /* …verbatim (colors kept as the CSS-var strings) … */ };
export const skillsGap: SkillsGap[] = [ /* …verbatim… */ ];
```
(The `trend.series[].color` / `modeMix[].color` values are `"var(--accent)"`/`"#9A7A18"` etc. — keep them as-is; they're consumed as CSS color strings by M1b charts.)

- [ ] **Step 3: Write the failing logic tests**

`apps/web/src/lib/seed/logic.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { jobs, lenses } from "@/lib/seed/data";
import {
  filterByLens, scoreForLens, deriveLensSummaries, sortJobs,
} from "@/lib/seed/logic";

describe("filterByLens", () => {
  it("all → every job", () => {
    expect(filterByLens(jobs, "all")).toHaveLength(13);
  });
  it("spain → only ES jobs", () => {
    expect(filterByLens(jobs, "spain").map((j) => j.id).sort()).toEqual(["j13", "j7"]);
  });
  it("berlin → only Berlin jobs", () => {
    expect(filterByLens(jobs, "berlin").map((j) => j.id).sort()).toEqual(["j11", "j12"]);
  });
  it("foreign → hq != country", () => {
    expect(filterByLens(jobs, "foreign").map((j) => j.id).sort()).toEqual(
      ["j3", "j4", "j5", "j7", "j8"],
    );
  });
});

describe("scoreForLens", () => {
  it("keeps role/skill lens-independent and recomputes loc+match per lens", () => {
    const j1 = jobs.find((j) => j.id === "j1")!;
    const all = scoreForLens(j1, "all");
    const remote = scoreForLens(j1, "remote");
    expect(all.factors.role).toBe(remote.factors.role); // 96
    expect(all.factors.skill).toBe(remote.factors.skill); // 89
    expect(remote.factors.loc).not.toBe(all.factors.loc); // loc changes
    expect(remote.match).toBe(87); // 0.4*96 + 0.4*89 + 0.2*64
  });
  it("caps match and flags when skill < 45", () => {
    const j5 = jobs.find((j) => j.id === "j5")!; // Sereact, skill 41
    const s = scoreForLens(j5, "remote");
    expect(s.redFlag).toBeTruthy();
    expect(s.match).toBeLessThanOrEqual(72);
  });
});

describe("deriveLensSummaries", () => {
  it("derives counts from the pool, not the prototype's hard-coded numbers", () => {
    const all = deriveLensSummaries(lenses, jobs).find((l) => l.id === "all")!;
    expect(all.count).toBe(13); // NOT 47
    expect(all.isNew).toBe(7); // count of isNew:true, NOT 11
  });
});

describe("sortJobs", () => {
  it("match sorts descending by match", () => {
    const sorted = sortJobs(jobs, "match");
    expect(sorted[0].match).toBeGreaterThanOrEqual(sorted[1].match);
  });
});
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/lib/seed/logic.test.ts
```
Expected: FAIL — `@/lib/seed/logic` not found.

- [ ] **Step 5: Implement the logic (ported from `data.jsx`)**

Create `apps/web/src/lib/seed/logic.ts`, porting `filterByLens`/`locForLens`/`scoreForLens` verbatim from `prototype/specula/data.jsx:310–362` (typed), plus `deriveLensSummaries` + `sortJobs`:
```ts
import type { Job, Lens, LensSummary, JobSort, Factors } from "@specula/shared-types";

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));

export function filterByLens(jobs: Job[], lensId: string): Job[] {
  if (lensId === "all") return jobs.slice();
  return jobs.filter((j) => {
    if (lensId === "remote") return j.mode === "Remote";
    if (lensId === "foreign") return j.hq !== j.country;
    if (lensId === "spain") return j.country === "ES";
    if (lensId === "berlin") return j.city === "Berlin";
    return true;
  });
}

export function locForLens(job: Job, lensId: string): number {
  if (lensId === "all") return job.factors.loc;
  const remote = job.mode === "Remote", hybrid = job.mode === "Hybrid";
  const euTz = ["NL", "DE", "FR", "ES", "IE", "PT", "BE", "AT"].includes(job.country);
  if (lensId === "remote") {
    let f = remote ? 92 : hybrid ? 58 : 32;
    f += euTz ? 6 : job.country === "GB" ? 0 : -6;
    return clamp(f);
  }
  if (lensId === "foreign") {
    let f = job.hq !== job.country ? 88 : 48;
    f += remote ? 6 : hybrid ? 0 : -6;
    return clamp(f);
  }
  if (lensId === "spain") {
    let f = job.country === "ES" ? 88 : 42;
    f += (job.city === "Barcelona" || job.city === "Madrid") ? 6 : 0;
    return clamp(f);
  }
  if (lensId === "berlin") {
    let f = job.city === "Berlin" ? 92 : job.country === "DE" ? 68 : 44;
    f += (hybrid || job.mode === "On-site") ? 4 : remote ? -8 : 0;
    return clamp(f);
  }
  return job.factors.loc;
}

export function scoreForLens(
  job: Job,
  lensId: string,
): { match: number; factors: Factors; redFlag?: string } {
  if (lensId === "all") return { match: job.match, factors: job.factors, redFlag: job.redFlag };
  const role = job.factors.role, skill = job.factors.skill;
  const loc = locForLens(job, lensId);
  let match = clamp(0.4 * role + 0.4 * skill + 0.2 * loc);
  let redFlag = job.redFlag;
  if (skill < 45) { redFlag = redFlag || "Low required-skill overlap"; match = Math.min(match, 72); }
  return { match, factors: { role, skill, loc }, redFlag };
}

export function deriveLensSummaries(lenses: Lens[], jobs: Job[]): LensSummary[] {
  return lenses.map((lens) => {
    const pool = filterByLens(jobs, lens.id);
    return { ...lens, count: pool.length, isNew: pool.filter((j) => j.isNew).length };
  });
}

export function sortJobs(jobs: Job[], sort: JobSort): Job[] {
  const out = jobs.slice();
  if (sort === "match") out.sort((a, b) => b.match - a.match);
  else if (sort === "deadline") out.sort((a, b) => a.deadlineDays - b.deadlineDays);
  else if (sort === "new") out.sort((a, b) => Number(b.isNew) - Number(a.isNew));
  return out;
}
```
> Note: `scoreForLens` returns lens-adjusted values; applying them to the returned jobs (mapping `match`/`factors`/`redFlag` onto each job) happens in the stub route (Task 3).

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/lib/seed/logic.test.ts
```
Expected: PASS — all filterByLens/scoreForLens/deriveLensSummaries/sortJobs cases green.

- [ ] **Step 7: Verify gates**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm test && pnpm lint && pnpm typecheck && pnpm format:check
cd /Users/jorisrombouts/Projects/Personal/specula/packages/shared-types && pnpm typecheck
```
Expected: all green (run `pnpm format` if `format:check` flags the seed file). The shared-types package type-checks standalone.

- [ ] **Step 8: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add packages/shared-types apps/web/src/lib/seed
git commit -m "feat(web): shared-types domain model + ported seed data and lens logic"
```

---

### Task 3: Stubbed API routes

**Files:**
- Create: the 8 `apps/web/src/app/api/*/route.ts` handlers + `apps/web/src/app/api/jobs/route.test.ts`

**Interfaces:**
- Consumes: `@/lib/seed/data` + `@/lib/seed/logic` (Task 2); `@specula/shared-types`.
- Produces: GET routes returning typed JSON (the M2 REST contract).

- [ ] **Step 1: Write failing route tests (jobs — the one with logic)**

`apps/web/src/app/api/jobs/route.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { GET } from "@/app/api/jobs/route";
import type { JobsResponse } from "@specula/shared-types";

async function call(url: string): Promise<JobsResponse> {
  const res = await GET(new Request(url));
  expect(res.status).toBe(200);
  return (await res.json()) as JobsResponse;
}

describe("GET /api/jobs", () => {
  it("all lens returns the full pool + derived lens summaries (not hard-coded)", async () => {
    const body = await call("http://localhost/api/jobs?lens=all&sort=match");
    expect(body.jobs).toHaveLength(13);
    const all = body.lenses.find((l) => l.id === "all")!;
    expect(all.count).toBe(13);
    expect(all.isNew).toBe(7);
    expect(body.sort).toBe("match");
  });
  it("foreign lens filters to hq!=country and re-scores loc", async () => {
    const body = await call("http://localhost/api/jobs?lens=foreign&sort=match");
    expect(body.jobs.map((j) => j.id).sort()).toEqual(["j3", "j4", "j5", "j7", "j8"]);
  });
  it("sorts by match descending", async () => {
    const body = await call("http://localhost/api/jobs?lens=all&sort=match");
    expect(body.jobs[0].match).toBeGreaterThanOrEqual(body.jobs[1].match);
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/app/api/jobs/route.test.ts
```
Expected: FAIL — `@/app/api/jobs/route` not found.

- [ ] **Step 3: Implement the jobs route**

`apps/web/src/app/api/jobs/route.ts`:
```ts
import { NextResponse } from "next/server";
import type { JobSort, JobsResponse } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import { filterByLens, scoreForLens, deriveLensSummaries, sortJobs } from "@/lib/seed/logic";

export function GET(request: Request): NextResponse<JobsResponse> {
  const url = new URL(request.url);
  const lens = url.searchParams.get("lens") ?? "all";
  const sortParam = url.searchParams.get("sort");
  const sort: JobSort = sortParam === "deadline" || sortParam === "new" ? sortParam : "match";

  const scored = filterByLens(jobs, lens).map((job) => {
    const s = scoreForLens(job, lens);
    return { ...job, match: s.match, factors: s.factors, redFlag: s.redFlag };
  });

  return NextResponse.json({
    jobs: sortJobs(scored, sort),
    lenses: deriveLensSummaries(lenses, jobs),
    sort,
  });
}
```

- [ ] **Step 4: Implement the remaining GET routes**

`apps/web/src/app/api/jobs/[id]/route.ts`:
```ts
import { NextResponse } from "next/server";
import { jobs } from "@/lib/seed/data";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const job = jobs.find((j) => j.id === id);
  if (!job) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(job);
}
```
`apps/web/src/app/api/lenses/route.ts`:
```ts
import { NextResponse } from "next/server";
import { jobs, lenses } from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";

export function GET(): NextResponse {
  return NextResponse.json(deriveLensSummaries(lenses, jobs));
}
```
`apps/web/src/app/api/companies/route.ts`:
```ts
import { NextResponse } from "next/server";
import { companies } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(companies);
}
```
`apps/web/src/app/api/approvals/route.ts`:
```ts
import { NextResponse } from "next/server";
import { approvals } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(approvals);
}
```
`apps/web/src/app/api/insights/route.ts`:
```ts
import { NextResponse } from "next/server";
import { insights } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(insights);
}
```
`apps/web/src/app/api/candidate/route.ts`:
```ts
import { NextResponse } from "next/server";
import { candidate } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(candidate);
}
```
`apps/web/src/app/api/targeting/route.ts`:
```ts
import { NextResponse } from "next/server";
import { targeting } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(targeting);
}
```

- [ ] **Step 5: Run tests + verify all routes build**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm test src/app/api/jobs/route.test.ts
pnpm lint && pnpm typecheck && pnpm build
```
Expected: jobs route tests PASS; lint/tsc clean; `pnpm build` lists the 8 `/api/*` routes (+ the existing `/api/auth`). Run `pnpm format` if needed.

- [ ] **Step 6: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web/src/app/api
git commit -m "feat(web): stubbed GET API routes serving typed seed with derived counts"
```

---

### Task 4: Atoms — MatchMeter, OverlapBar, useCountUp

**Files:**
- Create: `apps/web/src/lib/use-count-up.ts` (+ test), `apps/web/src/components/atoms/match-meter.tsx` (+ test), `apps/web/src/components/atoms/overlap-bar.tsx` (+ test)

**Interfaces:**
- Consumes: `@specula/shared-types` (`Job`), the M0a Tailwind tokens.
- Produces: `useCountUp(target, run, dur?)`; `<MatchMeter job mstyle? replay? reveal? countUp? />` (`mstyle: "bars"|"figure"|"ring"`); `<OverlapBar overlap={[number,number]} />`; `matchColor(job)`.

Port structure/logic from `prototype/specula/ui.jsx`; match the values in `prototype/specula/specula.css` (`.meter*`/`.bars`/`.bar-*`/`.ring*`) and `views.css` (`.jov*`) using Tailwind utilities + M0a tokens. `matchColor`: `redFlag` → `text-warn`; `match ≥ 85` → `text-accent`; else `text-ink`; any factor `< 50` → that bar `bg-warn`.

- [ ] **Step 1: Write the failing useCountUp test**

`apps/web/src/lib/use-count-up.test.ts`:
```ts
import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { useCountUp } from "@/lib/use-count-up";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("useCountUp", () => {
  it("returns 0 when not running", () => {
    const { result } = renderHook(() => useCountUp(94, false, 640));
    expect(result.current).toBe(0);
  });

  it("counts up to the target and stops", () => {
    // Mock RAF to invoke the callback SYNCHRONOUSLY with an increasing timestamp
    // that jumps past the duration by the 2nd frame, so the loop terminates:
    //   frame 1 → step(700): sets start=700, progress 0;
    //   frame 2 → step(1400): progress (1400-700)/640 > 1 → sets target, no further RAF.
    let now = 0;
    vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation((cb: FrameRequestCallback) => {
      now += 700;
      cb(now);
      return 0;
    });
    vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => {});
    const { result } = renderHook(() => useCountUp(94, true, 640));
    expect(result.current).toBe(94);
  });
});
```
> NOTE: the earlier draft of this test used a mock that always passed the same
> timestamp (`1e6`), so `start === t` every frame → progress stuck at 0 → infinite
> loop. The synchronous increasing-timestamp mock above terminates deterministically.
> Do **not** change `use-count-up.ts` to make this pass — the hook is a verbatim port
> of `ui.jsx`; fix belongs in the test.

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/lib/use-count-up.test.ts
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement useCountUp (ported from ui.jsx)**

`apps/web/src/lib/use-count-up.ts`:
```ts
"use client";

import { useEffect, useState } from "react";

export function useCountUp(target: number, run: boolean, dur = 900): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) {
      setV(0);
      return;
    }
    let raf = 0;
    let start = 0;
    const step = (t: number) => {
      if (!start) start = t;
      const p = Math.min((t - start) / dur, 1);
      const e = 1 - Math.pow(1 - p, 3);
      setV(Math.round(target * e));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, run, dur]);
  return v;
}
```

- [ ] **Step 4: Run to verify pass**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/lib/use-count-up.test.ts
```
Expected: PASS.

- [ ] **Step 5: Write the failing OverlapBar test**

`apps/web/src/components/atoms/overlap-bar.test.tsx`:
```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { OverlapBar } from "@/components/atoms/overlap-bar";

afterEach(cleanup);

describe("OverlapBar", () => {
  it("renders [m/n] req. skills", () => {
    render(<OverlapBar overlap={[8, 9]} />);
    expect(screen.getByText(/\[8\/9\] req\. skills/)).toBeInTheDocument();
  });
  it("is marked low when the ratio < 0.4", () => {
    const { container } = render(<OverlapBar overlap={[2, 8]} />);
    expect(container.querySelector('[data-low="true"]')).not.toBeNull();
  });
  it("is not low when the ratio >= 0.4", () => {
    const { container } = render(<OverlapBar overlap={[8, 9]} />);
    expect(container.querySelector('[data-low="true"]')).toBeNull();
  });
});
```

- [ ] **Step 6: Run to verify failure, then implement OverlapBar**

Run:
```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/components/atoms/overlap-bar.test.tsx
```
Expected: FAIL — module not found. Then create `apps/web/src/components/atoms/overlap-bar.tsx` (matches `views.css` `.jov`: 42×5 track, accent fill, warn when low):
```tsx
export function OverlapBar({ overlap }: { overlap: [number, number] }) {
  const [matched, total] = overlap;
  const low = matched / total < 0.4;
  const pct = (matched / total) * 100;
  return (
    <span
      data-low={low}
      className={`inline-flex items-center gap-[7px] font-medium ${low ? "text-warn" : "text-ink"}`}
    >
      <span className="h-[5px] w-[42px] overflow-hidden rounded-[3px] bg-panel-2">
        <span
          className={`block h-full ${low ? "bg-warn" : "bg-accent"}`}
          style={{ width: `${pct}%` }}
        />
      </span>
      [{matched}/{total}] req. skills
    </span>
  );
}
```
Re-run the test → PASS.

- [ ] **Step 7: Write the failing MatchMeter test**

`apps/web/src/components/atoms/match-meter.test.tsx`:
```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MatchMeter, matchColor } from "@/components/atoms/match-meter";
import type { Job } from "@specula/shared-types";

afterEach(cleanup);

const base = {
  id: "t1", company: "X", logo: "X", title: "T", city: "C", country: "NL", hq: "NL",
  mode: "Remote", flag: "🇳🇱", match: 90, factors: { role: 96, skill: 89, loc: 92 },
  overlap: [8, 9], seniority: "Senior", edu: "MSc", deadlineDays: 9, salary: null,
  posted: "1d ago", status: null, isNew: true, stillOpen: true, originVerified: true,
  hqConf: 98, stack: [], niceToHave: [], visa: "", langs: [], contract: "", geo: "",
  confidence: 90, responsibilities: [], summary: "", rationale: "",
} as unknown as Job;

describe("matchColor", () => {
  it("warn when redFlag", () => {
    expect(matchColor({ ...base, redFlag: "x" })).toBe("text-warn");
  });
  it("accent when match >= 85 and no red flag", () => {
    expect(matchColor({ ...base, match: 90 })).toBe("text-accent");
  });
  it("ink otherwise", () => {
    expect(matchColor({ ...base, match: 70 })).toBe("text-ink");
  });
});

describe("MatchMeter", () => {
  it("bars style shows the match number and ROLE/SKILL/LOC", () => {
    render(<MatchMeter job={base} mstyle="bars" />);
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.getByText("ROLE")).toBeInTheDocument();
    expect(screen.getByText("SKILL")).toBeInTheDocument();
    expect(screen.getByText("LOC")).toBeInTheDocument();
  });
  it("figure style shows the number without the factor rows", () => {
    render(<MatchMeter job={base} mstyle="figure" />);
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.queryByText("ROLE")).toBeNull();
  });
});
```

- [ ] **Step 8: Run to verify failure, then implement MatchMeter**

Run the test (FAIL — module not found). Then create `apps/web/src/components/atoms/match-meter.tsx`. Port the 3-style structure from `ui.jsx` `MatchMeter`, matching `specula.css` `.meter*`/`.bars`/`.ring*` values, using Tailwind + the M0a tokens. `"use client"` (it uses state/effects for reveal/countUp). Keep the `reveal`/`replay`/`countUp` props (M1a: `countUp` works via `useCountUp`; `reveal`/`replay` are accepted and render the final value — full animation wiring is M1c). Skeleton (fill styling to match the CSS exactly):
```tsx
"use client";

import { useEffect, useState } from "react";
import type { Job } from "@specula/shared-types";
import { useCountUp } from "@/lib/use-count-up";

export function matchColor(job: Job): string {
  if (job.redFlag) return "text-warn";
  if (job.match >= 85) return "text-accent";
  return "text-ink";
}

type Props = {
  job: Job;
  mstyle?: "bars" | "figure" | "ring";
  replay?: string | number;
  reveal?: boolean;
  countUp?: boolean;
};

export function MatchMeter({ job, mstyle = "bars", replay, reveal = false, countUp = false }: Props) {
  const col = matchColor(job);
  const segs: [string, number][] = [["ROLE", job.factors.role], ["SKILL", job.factors.skill], ["LOC", job.factors.loc]];
  const [shown, setShown] = useState(false);
  const [done, setDone] = useState(false);
  useEffect(() => {
    setShown(false); setDone(false);
    const t = setTimeout(() => setShown(true), reveal ? 320 : 40);
    return () => clearTimeout(t);
  }, [replay, reveal]);
  useEffect(() => {
    if (!shown) return;
    const t = setTimeout(() => setDone(true), reveal ? 820 : 0);
    return () => clearTimeout(t);
  }, [shown, reveal]);
  const counting = countUp || reveal;
  const num = useCountUp(job.match, shown && counting, reveal ? 780 : 640);
  const display = counting ? num : job.match;
  // Render `bars` | `figure` | `ring` per `mstyle`, matching specula.css:
  //  - bars: meter-num (mono 36px, `${col}`) + "/100" + label ("scoring…" when reveal && !done, else "match index"),
  //          then 3 bar-rows (grid 36px/1fr/24px; track h-[7px] bg-panel-2; fill width=shown?v:0%, bg-warn if v<50 else col);
  //  - figure: just the number at 54px, no bars;
  //  - ring: conic-gradient ring (74px) with number centered + `R·{v} S·{v} L·{v}` factor list.
  // Use `data-style={mstyle}` on the root for parity with the prototype. Fill the JSX to match the CSS values exactly.
  return (/* … the three styles … */ null);
}
```
> The implementer completes the JSX for all three styles from `ui.jsx` + `specula.css`. Tests assert `bars` shows the number + ROLE/SKILL/LOC and `figure` hides the factor rows — both must pass. Re-run the test → PASS.

- [ ] **Step 9: Verify gates**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm test && pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```
Expected: all atom tests pass; gates clean; build succeeds.

- [ ] **Step 10: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web/src/lib/use-count-up.ts apps/web/src/lib/use-count-up.test.ts apps/web/src/components/atoms
git commit -m "feat(web): MatchMeter (3 styles), OverlapBar, and useCountUp atoms"
```

---

### Task 5: Vocabulary atoms + TagEditor + /preview gallery

**Files:**
- Create: `apps/web/src/components/atoms/{chip,tag,button,toggle,tag-editor}.tsx`, `apps/web/src/components/atoms/tag-editor.test.tsx`, `apps/web/src/app/preview/page.tsx`

**Interfaces:**
- Consumes: the atoms from Task 4; M0a tokens.
- Produces: `<Chip>`, `<Tag variant>`, `<Button variant>`, `<Toggle on onChange>`, `<TagEditor values onChange kind? />`; the `/preview` gallery route.

Match `specula.css` (`.chip`/`.btn*`/`.tag-*`) and `views.css` (`.toggle`, `.tagchip*`/`.tag-add`) values with Tailwind + M0a tokens.

- [ ] **Step 1: Build the simple presentational atoms**

`apps/web/src/components/atoms/chip.tsx`:
```tsx
export function Chip({ children, mono = false }: { children: React.ReactNode; mono?: boolean }) {
  return (
    <span
      className={`rounded-[6px] border border-rule bg-paper px-[9px] py-[3px] text-ink-2 ${mono ? "font-mono text-[10.5px]" : "text-[11.5px]"}`}
    >
      {children}
    </span>
  );
}
```
`apps/web/src/components/atoms/button.tsx` (variants `btn`/`pri`/`accent`/`ghost` per specula.css):
```tsx
type Variant = "default" | "pri" | "accent" | "ghost";
const cls: Record<Variant, string> = {
  default: "border-rule-2 bg-card text-ink hover:border-ink",
  pri: "border-ink bg-ink text-paper hover:bg-black",
  accent: "border-accent bg-accent text-white",
  ghost: "border-transparent bg-transparent text-ink-2 hover:bg-panel hover:text-ink",
};
export function Button({
  variant = "default", className = "", ...props
}: { variant?: Variant } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex items-center gap-[7px] rounded-[7px] border px-[14px] py-2 text-[12.5px] font-medium transition-colors ${cls[variant]} ${className}`}
      {...props}
    />
  );
}
```
`apps/web/src/components/atoms/tag.tsx` (variants `new`/`status`/`flag` per specula.css):
```tsx
export function Tag({ variant, children }: { variant: "new" | "status" | "flag"; children: React.ReactNode }) {
  if (variant === "new")
    return (
      <span className="font-mono inline-flex items-center gap-1 text-[9px] tracking-[0.06em] text-accent-ink before:h-[5px] before:w-[5px] before:rounded-full before:bg-accent before:content-['']">
        {children}
      </span>
    );
  if (variant === "flag")
    return <span className="font-mono text-[10.5px] text-warn">{children}</span>;
  return (
    <span className="font-mono rounded-[3px] border border-ink-2 px-[7px] py-[2px] text-[9px] uppercase tracking-[0.05em] text-ink">
      {children}
    </span>
  );
}
```
`apps/web/src/components/atoms/toggle.tsx` (views.css `.toggle`: 38×22, knob 18, translateX 16):
```tsx
export function Toggle({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={`relative h-[22px] w-[38px] flex-shrink-0 rounded-[20px] transition-colors ${on ? "bg-accent" : "bg-rule-2"}`}
    >
      <span
        className={`absolute left-[2px] top-[2px] h-[18px] w-[18px] rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,0.2)] transition-transform ${on ? "translate-x-[16px]" : ""}`}
      />
    </button>
  );
}
```

- [ ] **Step 2: Write the failing TagEditor test**

`apps/web/src/components/atoms/tag-editor.test.tsx`:
```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { TagEditor } from "@/components/atoms/tag-editor";

afterEach(cleanup);

describe("TagEditor", () => {
  it("renders the current values as chips", () => {
    render(<TagEditor values={["Python", "RAG"]} onChange={() => {}} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("RAG")).toBeInTheDocument();
  });
  it("removes a value on clicking its ×", () => {
    const onChange = vi.fn();
    render(<TagEditor values={["Python", "RAG"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /remove Python/i }));
    expect(onChange).toHaveBeenCalledWith(["RAG"]);
  });
  it("adds a value via the + add input on Enter", () => {
    const onChange = vi.fn();
    render(<TagEditor values={["Python"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "vLLM" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["Python", "vLLM"]);
  });
});
```

- [ ] **Step 3: Run to verify failure, then implement TagEditor**

Run (FAIL — module not found). Then `apps/web/src/components/atoms/tag-editor.tsx` (views.css `.tagchip`/`.tagchip-x`/`.tag-add`; `kind` variants `default`/`syn`/`avoid`):
```tsx
"use client";

import { useState } from "react";

type Kind = "default" | "syn" | "avoid";
const chipCls: Record<Kind, string> = {
  default: "border-rule bg-panel text-ink",
  syn: "border-ink bg-ink text-paper",
  avoid: "border-transparent bg-warn-bg text-warn",
};

export function TagEditor({
  values, onChange, kind = "default",
}: { values: string[]; onChange: (v: string[]) => void; kind?: Kind }) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const commit = () => {
    const v = draft.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setDraft(""); setAdding(false);
  };
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((v) => (
        <span
          key={v}
          className={`flex items-center gap-2 rounded-[7px] border px-3 py-[6px] text-[12.5px] ${chipCls[kind]}`}
        >
          {v}
          <button
            type="button"
            aria-label={`remove ${v}`}
            onClick={() => onChange(values.filter((x) => x !== v))}
            className="font-mono cursor-pointer text-ink-3"
          >
            ×
          </button>
        </span>
      ))}
      {adding ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && commit()}
          onBlur={commit}
          className="rounded-[7px] border border-rule-2 bg-card px-3 py-[6px] text-[12.5px] text-ink outline-none focus:border-ink"
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="rounded-[7px] border border-dashed border-rule-2 bg-transparent px-3 py-[6px] text-[12.5px] text-ink-2 hover:border-ink hover:text-ink"
        >
          + add
        </button>
      )}
    </div>
  );
}
```
Re-run the test → PASS.

- [ ] **Step 4: Build the `/preview` gallery**

`apps/web/src/app/preview/page.tsx` — a client page rendering each atom's variants against sample props (a couple of seed jobs for MatchMeter). Render: MatchMeter × {bars, figure, ring} for a high-match job and the red-flag job (j5); OverlapBar low + normal; Chip/Tag(new/status/flag)/Button(all variants)/Toggle (with local state); TagEditor (default + syn + avoid). Keep it simple (a dev tool), grouped under headings, `bg-paper` page. Example shape:
```tsx
"use client";

import { useState } from "react";
import { jobs } from "@/lib/seed/data";
import { MatchMeter } from "@/components/atoms/match-meter";
import { OverlapBar } from "@/components/atoms/overlap-bar";
import { Chip } from "@/components/atoms/chip";
import { Tag } from "@/components/atoms/tag";
import { Button } from "@/components/atoms/button";
import { Toggle } from "@/components/atoms/toggle";
import { TagEditor } from "@/components/atoms/tag-editor";

export default function PreviewPage() {
  const top = jobs.find((j) => j.id === "j1")!;
  const flagged = jobs.find((j) => j.id === "j5")!;
  const [on, setOn] = useState(true);
  const [tags, setTags] = useState(["Python", "RAG"]);
  return (
    <main className="min-h-screen bg-paper p-10 text-ink">
      <h1 className="font-display mb-8 text-[28px] font-semibold">Atom preview</h1>
      {/* MatchMeter × 3 styles for `top` and `flagged`; OverlapBar; Chip/Tag/Button/Toggle; TagEditor.
          Group each under a mono heading. */}
      <section className="flex flex-wrap gap-10">
        <MatchMeter job={top} mstyle="bars" />
        <MatchMeter job={top} mstyle="figure" />
        <MatchMeter job={top} mstyle="ring" />
        <MatchMeter job={flagged} mstyle="bars" />
      </section>
      <section className="mt-8 flex flex-col gap-4">
        <OverlapBar overlap={[8, 9]} />
        <OverlapBar overlap={[2, 8]} />
        <div className="flex gap-2">
          <Chip>chip</Chip>
          <Tag variant="new">NEW</Tag>
          <Tag variant="status">Saved</Tag>
          <Tag variant="flag">⚑ red flag</Tag>
        </div>
        <div className="flex gap-2">
          <Button>Default</Button>
          <Button variant="pri">Primary</Button>
          <Button variant="accent">Accent</Button>
          <Button variant="ghost">Ghost</Button>
        </div>
        <Toggle on={on} onChange={setOn} />
        <TagEditor values={tags} onChange={setTags} />
        <TagEditor values={["Data Scientist"]} onChange={() => {}} kind="syn" />
        <TagEditor values={["Relocation required"]} onChange={() => {}} kind="avoid" />
      </section>
    </main>
  );
}
```
(`/preview` is outside `(app)`, so the M0b auth guard doesn't gate it — it's a dev tool.)

- [ ] **Step 5: Verify gates + the gallery renders**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm test && pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```
Expected: TagEditor tests pass; gates clean; build lists `/preview`. (Optional manual check: `just dev-web` → open `http://localhost:3000/preview` and eyeball the atoms — no auth needed.)

- [ ] **Step 6: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web/src/components/atoms apps/web/src/app/preview
git commit -m "feat(web): vocabulary atoms (chip/tag/button/toggle), TagEditor, and /preview gallery"
```

---

## Self-Review

**1. Spec coverage** (design §1–§8):
- §2 workspace + shared-types → T1 (skeleton + wiring) + T2 (full types). §3 seed ported + logic → T2. §4 stub API routes (all 8, derived counts, lens-aware scoring) → T3. §5 derived-count deviation → enforced by T2 `deriveLensSummaries` + its test (asserts 13/7, not 47/11) + T3's route test. §6 atoms (MatchMeter ×3, OverlapBar, useCountUp, chips/tags/buttons/toggle, TagEditor, /preview) → T4 + T5. §7 testing → each task's Vitest + route tests + gate runs. §8 acceptance 1–6 → T1 (workspace/gates), T2 (seed/logic), T3 (routes), T4/T5 (atoms/preview), all-tasks (gates green). **All covered.**
- Invariants: derived counts (T2/T3 tests assert derived, not hard-coded); salary display-only (absent from `sortJobs`/`filterByLens`/`scoreForLens`); numbers-vs-prose (logic touches only numeric fields). Deferred (views/animations/tweaks/visual-regression/real-API) correctly absent.

**2. Placeholder scan:** No "TBD"/"add error handling". The two "port verbatim from the in-repo prototype" instructions (T2 seed data; T4/T5 exact styling) are **not** placeholders — the source files are in the repo and named exactly; re-transcribing 230 lines of seed / every CSS value in the plan would risk transcription errors. The MatchMeter JSX body is left for the implementer to complete from `ui.jsx`+`specula.css` with the tests (`bars` shows number+ROLE/SKILL/LOC; `figure` hides rows) as the gate — the structure, props, logic (matchColor/reveal/countUp), and CSS target are all given.

**3. Type consistency:** `Job`/`Lens`/`LensSummary`/`JobsResponse`/`JobSort`/`Factors` defined in T2 `shared-types` are the exact names imported by T2 `data.ts`/`logic.ts`, T3 routes/tests, and T4 atoms. `filterByLens`/`locForLens`/`scoreForLens`/`deriveLensSummaries`/`sortJobs` signatures in T2 match their T3 consumers. `useCountUp(target, run, dur?)` (T4) matches its MatchMeter use. `matchColor(job) → "text-warn"|"text-accent"|"text-ink"` consistent between T4 impl and test. Atom prop shapes (`OverlapBar overlap`, `Toggle {on,onChange}`, `TagEditor {values,onChange,kind}`) consistent between T4/T5 impls, tests, and the T5 gallery. **Consistent.**
