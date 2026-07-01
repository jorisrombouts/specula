# Specula M1a — Foundations (workspace · shared-types · seed · stub API · atoms): Design Spec

> **Status:** approved design, ready for `writing-plans`.
> **Milestone:** M1a — the first of four M1 sub-milestones. M1 (spec §18) = "port every view + the
> four signature moments pixel-faithfully against seeded data served by a stubbed API; visual-
> regression vs prototype passes." Decomposition: **M1a foundations** → M1b static views → M1c
> signature moments → M1d Tweaks panel + visual-regression.
> **Sources of truth:** prototype `prototype/specula/{data,ui}.jsx` (exact seed + atom behavior),
> prototype spec §3–§7, production spec §4/§6/§8/§10/§12, `CLAUDE.md` (invariants/deviations).
> **Conflict rule:** visuals → prototype wins; architecture/behavior → production spec wins.

---

## 1. Goal & boundary

Build everything M1b's views need before any view exists: the **pnpm workspace** + a
**`@specula/shared-types`** package, the **seed data** (ported 1:1 from the prototype), a **stubbed
API** serving that seed through the same typed REST contract M2 will back with real FastAPI, and the
shared **atoms** (MatchMeter, OverlapBar, useCountUp, the chip/tag/button/toggle vocabulary,
TagEditor) — plus a dev-only `/preview` gallery.

**In scope (M1a):**
1. Convert the repo to a **pnpm workspace**; add `packages/shared-types` (hand-authored domain types).
2. **Seed data** ported verbatim from `prototype/specula/data.jsx`, typed by `shared-types`.
3. **Stubbed API** route handlers matching the M2 REST contract (§8), returning typed seed data with
   **server-derived counts** and **lens-aware scoring** (ported `filterByLens`/`scoreForLens`).
4. **Atoms:** `MatchMeter` (3 styles), `OverlapBar`, `useCountUp`, chips/tags/buttons/toggle,
   `TagEditor` — pure, prop-driven, tested. Plus a dev-only `/preview` gallery.

**Out of scope (deferred, with owner):**
- The 8 full **views** (Jobs/Drawer/Approvals/Companies/Insights/Profiles/Candidate/Targeting) → **M1b**.
- The four **signature moments** (assembling intro, FLIP re-sort, scoring reveal, row→drawer morph) →
  **M1c**. (MatchMeter's `reveal`/`replay` animation modes are stubbed as props now, wired in M1c.)
- **Tweaks panel** + **visual-regression** suite → **M1d**.
- **Real API / DB / persistence / RLS / bootstrap** → **M2**. The stub API is the seam M2 fills.
- How views *consume* the API (RSC-fetch vs direct call, TanStack Query) → **M1b**.

**Invariants honored** (`CLAUDE.md` / spec §19):
- **Counts are DERIVED server-side, never stored/hard-coded.** The stub API computes lens counts +
  "new" counts from the seed pool via `filterByLens`; the prototype's hard-coded `lens.count`/`isNew`
  (47/11/…) are **not** served (see §5.3 for the resulting deviation from the prototype's numbers).
- **Salary never ranks or filters; shown only when stated.** `salary` is a display-only field
  (`string | null`); it is absent from all scoring/sorting/filtering in the seed logic and the stub.
- **Scores: numbers computed, prose generated.** In the seed, `match`/`factors` are numeric data and
  `rationale`/`summary` are prose — the stub never derives one from the other.

---

## 2. pnpm workspace + `@specula/shared-types`

### 2.1 Workspace conversion

- Add root **`pnpm-workspace.yaml`**: `packages: ["apps/web", "packages/*"]` — **not** `apps/api`
  (it stays a standalone **uv** Python project; the workspace is JS-only).
- Add a minimal root **`package.json`** (`private: true`, `name: "specula"`, `packageManager:
  "pnpm@9.15.4"`, maybe root scripts). The **single pnpm lockfile moves to the repo root**
  (`pnpm-lock.yaml`); `apps/web/pnpm-lock.yaml` is removed.
- `apps/web/package.json` adds the dependency `"@specula/shared-types": "workspace:*"`.

### 2.2 CI + justfile updates (integration — must stay green)

- **CI web job** (`.github/workflows/ci.yml`): install at the **root** (not `apps/web`) — the job
  no longer uses `working-directory: apps/web` for the install/cache steps. Concretely: `pnpm install
  --frozen-lockfile` at root; `cache-dependency-path: pnpm-lock.yaml` (root); build the types package
  first (`pnpm --filter @specula/shared-types build`), then run the web checks via `pnpm --filter web
  <lint|typecheck|build|test>` (or `cd apps/web && pnpm …` after a root install). The `AUTH_SECRET`
  job env (M0b) stays.
- **justfile:** `setup` installs at root (`pnpm install`) + builds shared-types; `dev-web`,
  `lint`/`typecheck`/`test` may need `pnpm --filter @specula/shared-types build` first so web
  type-checks against the built types (or configure TS project references / `tsconfig` paths so
  web resolves the package source directly in dev). The exact mechanism is a plan decision; the
  requirement is: `just lint/typecheck/test`, `just dev-web`, and CI all stay green post-conversion.

### 2.3 `packages/shared-types`

Hand-authored TypeScript types (M2 later regenerates from FastAPI's OpenAPI, per spec §8). A plain TS
package: `package.json` (name `@specula/shared-types`, a `build` = `tsc`), `tsconfig.json`, `src/`
exporting the domain model. Types mirror the prototype's `data.jsx` shapes (§4) **exactly** so the
seed is well-typed:

- `Job` — the full insight record: `id, company, logo, title, city, country, hq, mode, flag, match,
  factors: { role; skill; loc }, overlap: [number, number], seniority, edu, deadlineDays,
  salary: string | null, posted, status: JobStatus | null, isNew, stillOpen, originVerified, hqConf,
  redFlag?: string, stack: string[], niceToHave: string[], visa, langs: string[], contract, geo,
  confidence, dismissReason?: string, responsibilities: string[], summary, rationale`.
  `JobStatus = "Saved" | "Applied" | "Interviewing" | "Offer" | "Dismissed"`. `Mode = "Remote" |
  "Hybrid" | "On-site"`.
- `Lens` — `id, name, short, active, scope, modes: Mode[], origin, focus, seeds: string[]`. **No**
  `count`/`isNew` (derived — see §5).
- `Candidate`, `Targeting`, `Company`, `Approval`, `Insights` (with `SkillDemand`, `Trend`,
  `SeniorityMix`, `ModeMix`, `SalaryBand`, `ActiveCompany`), `SkillsGap` — one type per §4 shape.
- **API response types:** `LensSummary` (a `Lens` + derived `count`/`isNew`), `JobsResponse`
  (`{ jobs: Job[]; lenses: LensSummary[]; sort: JobSort }`), `JobSort = "match" | "deadline" | "new"`.
  These are the contract M1b's views + M2's real API both honor.

---

## 3. Seed data (ported 1:1)

Port `prototype/specula/data.jsx` **verbatim** into typed TS in `apps/web` (e.g.
`apps/web/src/lib/seed/`): `candidate`, `targeting`, `lenses` (5), `jobs` (13), `companies` (10),
`approvals` (6), `insights`, `skillsGap`. Values are copied exactly (same personas, companies,
numbers, prose) so M1d's visual-regression matches the prototype. This is data, not logic — typed by
`shared-types`, no transformation.

Also port the **scoring/filtering logic** from `data.jsx` (this IS logic — unit-tested):
- `filterByLens(jobs, lensId)` — §4.6: `all` → all; `remote` → `mode==="Remote"`; `foreign` →
  `hq!==country`; `spain` → `country==="ES"`; `berlin` → `city==="Berlin"` (+ the `modes` gate).
- `locForLens(job, lensId)` + `scoreForLens(job, lensId)` — §6.2 lens-aware scoring: role & skill
  factors are **lens-independent**; the **loc factor and overall `match` are recomputed per lens**
  (`0.4·role + 0.4·skill + 0.2·loc`, with the one-way red-flag cap when `skill < 45`). Ported exactly
  from `data.jsx:310–348`. This makes lens switching genuinely re-score (honest for M1c's FLIP).

---

## 4. Stubbed API routes

Next route handlers under `apps/web/src/app/api/` matching the M2 REST contract (§8). Each returns
JSON typed by `@specula/shared-types`, reading the seed and applying the ported logic **server-side**:

| Route | Returns |
|---|---|
| `GET /api/jobs?lens={id}&sort={match\|deadline\|new}` | `JobsResponse`: the lens-filtered pool with **lens-aware** `match`/`factors`/`redFlag` applied (`scoreForLens`), sorted; **plus every lens with derived `count`/`isNew`** (`LensSummary[]`). |
| `GET /api/jobs/{id}` | one `Job` (full insight record). |
| `GET /api/lenses` | `LensSummary[]` (lenses + derived counts). |
| `GET /api/companies` | `Company[]`. |
| `GET /api/approvals` | `Approval[]`. |
| `GET /api/insights?period=…` | `Insights`. |
| `GET /api/candidate` | `Candidate`. |
| `GET /api/targeting` | `Targeting`. |

Notes:
- These are **GET-only stubs** in M1a (read surface). Mutations (PATCH state, POST decision, PUT
  candidate/targeting, POST runs) arrive with the views/persistence that need them (M1b/M2).
- The routes live at `/api/*` under `apps/web`. They coexist with `/api/auth/*` (Auth.js). Whether
  M1b's views are guarded/consume these via RSC or client fetch is an M1b decision; the stub is a
  plain public read surface of seed data for now.
- **Derived counts (invariant):** `count` = `filterByLens(jobs, lens.id).length`; `isNew` = count of
  those with `isNew === true`. Never read from the seed's hard-coded lens fields.

---

## 5. Derived-count deviation from the prototype — flag for M1b/M1d

The prototype's lens bar displays hard-coded numbers (All "47 · 11 new", Remote "23 · 6", …) for an
imagined larger pool, but the actual seed has **13 jobs**. Deriving honestly (the invariant) yields
small real counts (e.g. All = 13; Spain = 2; Berlin = 2). **This is intentional** — the derived-counts
invariant (architecture/behavior → spec wins) overrides the prototype's cosmetic numbers. Consequence
for later: M1d's visual-regression baseline for the count-bearing regions (lens bar, "N new" badges,
Profiles counts) must be captured from **M1's own rendering**, not pixel-diffed against the
prototype's 47/11. Layout/typography still match the prototype 1:1; only the count *values* differ.
(Recorded here so M1b/M1d don't "fix" it back to hard-coded numbers.)

---

## 6. Shared atoms

Ported from `prototype/specula/ui.jsx` to typed React components (props from `shared-types`), pure and
prop-driven, styled with the M0a Tailwind tokens. Behavior copied exactly:

- **`MatchMeter`** (`{ job, mstyle, replay, reveal, countUp }`): 3 styles — `bars` (number + /100 +
  ROLE/SKILL/LOC tracks), `figure` (big number only), `ring` (conic-gradient ring + compact factor
  list). `matchColor`: `redFlag` → warn; `match ≥ 85` → accent; else ink; any factor `< 50` → that
  bar warn. **M1a delivers the static render + `countUp`** (via `useCountUp`). The `reveal` (drawer
  "scoring…") and `replay` (FLIP re-sweep) modes are present as props/typed but their animation
  wiring to the signature moments is **M1c** — in M1a they render the final value.
- **`OverlapBar`** (`{ overlap: [number, number] }`): inline `[m/n] req. skills` + mini fill;
  `low` (warn) when `overlap[0]/overlap[1] < 0.4`.
- **`useCountUp(target, run, dur)`**: rAF cubic-ease-out integer count-up (verbatim from `ui.jsx`).
- **Vocabulary atoms** (prototype §3, `views.css`): `Chip`/`ChipMono`, `Tag` variants
  (`tag-new`/`tag-status`/`tag-flag`), `Button` variants (`btn`/`btn-pri`/`btn-accent`/`btn-ghost`),
  `Toggle` (38×22 pill). Built as needed by the atoms/preview; the full set is completed as M1b
  views demand them — M1a ships the ones the `/preview` gallery exercises (MatchMeter, OverlapBar,
  chips/tags/buttons/toggle) + **`TagEditor`** (removable chips + inline "+ add", `kind` variants
  `syn`/`avoid`) since it's a shared control several M1b views need.
- **`Icon`** already exists (M0a) — reused, not rebuilt.

**`/preview` gallery:** a dev-only route (`apps/web/src/app/preview/page.tsx`) rendering each atom's
variants (MatchMeter × 3 styles × color states, OverlapBar low/normal, the chips/tags/buttons/toggle,
TagEditor). Aids atom development and gives M1d a stable visual target. It renders static props (no
network); it's outside `(app)` so the auth guard doesn't gate it (it's a dev tool). *(Plan may choose
to gate/omit it in production builds; not required for M1a.)*

---

## 7. Testing

- **Vitest (logic):** `filterByLens` (each lens returns the right subset over the 13-job seed);
  `scoreForLens`/`locForLens` (role/skill lens-independent; loc + match change per lens; red-flag cap
  at `skill < 45`); derived counts (`count`/`isNew` match `filterByLens`, and are NOT the seed's
  hard-coded values).
- **Vitest (atoms):** MatchMeter renders each style + `matchColor` logic (redFlag→warn, ≥85→accent,
  factor<50→warn bar) + `useCountUp` reaches target; OverlapBar `low` threshold; TagEditor add/remove.
- **Route-handler tests:** each stub route returns the correct shape (typed) + status 200; `/api/jobs`
  applies lens filtering + lens-aware scoring + derived counts + sort; `/api/jobs/{id}` returns the
  right job / 404 for unknown.
- **Types:** `@specula/shared-types` compiles (`tsc`); `apps/web` type-checks against it.
- **Gates:** `just lint/typecheck/test` + `pnpm build` + `pre-commit` stay green **through the
  workspace conversion**; CI (both jobs) green with the root-install changes.

---

## 8. Acceptance (M1a definition of done)

1. Repo is a pnpm workspace: root `pnpm-workspace.yaml` + root `package.json` + single root lockfile;
   `@specula/shared-types` builds; `apps/web` depends on it via `workspace:*` and type-checks green.
2. Seed data (candidate, targeting, 5 lenses, 13 jobs, 10 companies, 6 approvals, insights, skillsGap)
   is ported verbatim, typed, and the ported `filterByLens`/`scoreForLens` logic is unit-tested.
3. All 8 GET stub routes return typed seed data; `/api/jobs` applies lens filtering + lens-aware
   scoring + **derived** counts + sort; counts are computed, never read from hard-coded lens fields.
4. Atoms (MatchMeter ×3 styles, OverlapBar, useCountUp, chips/tags/buttons/toggle, TagEditor) render
   and pass unit tests; the `/preview` gallery renders every atom variant.
5. `just lint && just typecheck && just test` + `pnpm build` + `pre-commit run --all-files` green;
   CI (api + web) green with the workspace/root-install changes.
6. No views, no signature-moment animations, no Tweaks panel, no visual-regression, no real API/DB
   (all correctly deferred).

---

## 9. Open considerations for the plan

- **Workspace resolution in dev/typecheck:** whether `apps/web` consumes `@specula/shared-types` via
  its built output (`tsc` build step first) or via TS project references / `tsconfig` `paths` to the
  source. Pick the lowest-friction option that keeps `just typecheck` and hot-reload working; state it.
- **CI shape:** root install + `--filter` vs keeping per-app steps after a root install. Either is
  fine; the plan picks one and keeps both jobs green.
- **`/preview` in production:** gate behind `NODE_ENV !== "production"` or a route segment config, or
  leave it (harmless). Plan decides; not an M1a blocker.
- The **derived-count deviation** (§5) is decided (derive, don't hard-code) — carried forward to
  M1b/M1d so it isn't "corrected" back to the prototype's cosmetic numbers.
- Everything else is specified; no TBDs.
