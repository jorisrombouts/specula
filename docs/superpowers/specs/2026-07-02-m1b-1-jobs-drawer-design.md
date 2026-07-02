# Specula M1b-1 — Jobs view + Drawer (static): Design Spec

> **Status:** approved design, ready for `writing-plans`.
> **Milestone:** M1b-1 — the first of three M1b sub-pieces (M1b = "static views"). Decomposition:
> **M1b-1 Jobs + Drawer** → M1b-2 Approvals + Companies + Insights → M1b-3 Profiles + Candidate +
> Targeting. M1b sits between M1a (foundations: workspace, seed, stub API, atoms) and M1c (the four
> signature moments) / M2 (persistence).
> **Sources of truth:** prototype `prototype/specula/jobs.jsx` (component structure), `views.css` +
> `specula.css` (styling values), prototype spec §7.1–§7.2, production spec §10, `CLAUDE.md`.
> **Conflict rule:** visuals → prototype wins; architecture/behavior → production spec wins.

---

## 1. Goal & boundary

Port the prototype's **Jobs view + detail Drawer** — the product centerpiece — to typed React against
the M1a seed/atoms, **statically**: pixel-faithful structure, real derived data, an openable drawer.
No signature-moment animations (M1c), no persisting interactivity (M2).

**In scope (M1b-1):**
1. A **typed data-access layer** (`lib/api/`): `getJobsPool()`, `getLenses()`, `getCandidate()`
   (+ `getJob(id)`), server functions over the M1a seed logic. The M1a `/api/*` routes are refactored
   to call the same functions (DRY — one source of the orchestration).
2. The **Jobs page** (RSC) → a client **`JobsView`**: view header (derived pool/new counts), the
   **lens bar** (derived per-lens counts), **deadline banner**, **toolbar** (active lens rules + sort),
   **column header**, the **job rows**, and the drawer open/close state. Lens + sort switch
   **client-side** (see §3).
3. **`JobRow`**: the 3-col grid (index / body / MatchMeter) with title + NEW/status tags, meta line,
   rationale, and footer (OverlapBar, top-5 stack, deadline, red-flag / origin-unverified). Click →
   opens the Drawer.
4. The **Drawer**: all §7.2 sections rendered from the job's insight record — Match, Summary, Skills
   (have/missing), Insight record (+ extraction confidence), Responsibilities, Application status,
   Feedback, footer. **Static** (plain slide-in; no morph/reveal). Open/close is the only interactivity.

**Out of scope (deferred, with owner):**
- The **four signature moments** — assembling intro, **FLIP lens re-sort**, **scoring reveal**,
  **row→drawer morph** — and all entrance animations (rowIn/viewIn stagger) + reduced-motion → **M1c**.
  In M1b-1 the MatchMeter shows its final value; the drawer plain-slides in; rows render static.
- **Persisting/mutating interactivity** — changing application status, feedback like/dismiss, save,
  note editing, row-dismiss removal → **M2** ("state persists via the API", spec §10). In M1b-1 these
  controls render for visual fidelity but are **display-only / inert** (they show the seed's current
  state; wiring is M2).
- The other 6 views → M1b-2 / M1b-3. Real API/DB → M2.

**Invariants honored** (`CLAUDE.md`): **counts derived** (the lens bar, pool/new header counts, and
"N new" come from `filterByLens` over the pool — the derived 13/7-style values, never hard-coded).
**Salary display-only** — shown in the row meta + insight record when present ("not stated in ad"
otherwise); never sorts/filters/scores. **Numbers computed, prose generated** — `match`/`factors` are
data; `rationale`/`summary` are prose; the view never derives one from the other.

---

## 2. Files

```
apps/web/src/
  lib/api/
    jobs.ts            # CREATE — getJobsPool(), getJob(id), getJobs(lens, sort) [JobsResponse]
    lenses.ts          # CREATE — getLenses()
    candidate.ts       # CREATE — getCandidate()
    (M1b-2/3 add companies.ts, approvals.ts, insights.ts, targeting.ts)
  app/api/jobs/route.ts          # MODIFY — call getJobs() (DRY)
  app/api/jobs/[id]/route.ts     # MODIFY — call getJob()
  app/api/lenses/route.ts        # MODIFY — call getLenses()
  app/api/candidate/route.ts     # MODIFY — call getCandidate()
  app/(app)/jobs/page.tsx        # MODIFY — RSC: fetch pool/lenses/candidate → <JobsView>
  components/jobs/
    jobs-view.tsx                # CREATE (client) — lens bar, toolbar, list, drawer state
    job-row.tsx                  # CREATE — one row (+ MatchMeter)
    lens-bar.tsx                 # CREATE — the segmented lens control (derived counts)
    job-drawer.tsx               # CREATE (client) — the detail drawer (all sections)
    drawer-sections.tsx          # CREATE — InsightRecord, SkillsSplit, Lifecycle, Feedback (display)
    skills.ts                    # CREATE — candidateHas() fuzzy match + have/missing split
  components/jobs/*.test.tsx     # CREATE — Vitest component tests
```

Rationale for the split: `jobs.jsx` is 409 lines doing everything; splitting by responsibility
(row / lens-bar / drawer / drawer-sections / skill-logic) keeps each file focused and testable.

---

## 3. Data flow (RSC initial fetch → client interactivity)

- **`lib/api/` data-access layer** wraps the M1a seed logic in typed server functions:
  `getJobsPool(): Job[]` (the full pool, base-scored — lens-independent), `getLenses(): Lens[]`,
  `getCandidate(): Candidate`, `getJob(id): Job | null`, and `getJobs(lens, sort): JobsResponse`
  (the filter→score→sort→derive orchestration, used by the `/api/jobs` route). Today these read the
  seed; **M2 swaps the bodies to BFF→FastAPI**. The M1a routes are refactored to call them (DRY).
- **`jobs/page.tsx` (RSC)** calls `getJobsPool()` + `getLenses()` + `getCandidate()` and passes them
  as props to the client `<JobsView>`. This is the SSR fast-first-paint the spec (§10) wants.
- **`<JobsView>` (client)** holds the pool + does lens/sort **client-side**: it re-applies
  `filterByLens` + `scoreForLens` + `sortJobs` (the M1a **pure** logic, importable client-side) on
  lens/sort change, and computes lens-bar counts via `filterByLens` per lens. **Why client-side, not
  URL/RSC-re-render:** the rows must persist in the DOM for M1c's FLIP to animate old→new positions;
  a full RSC re-render replaces the DOM and forecloses the FLIP. Client state = M1c drops FLIP in
  with zero rework. (This corrects the earlier "lens via URL" framing.)
- The **`/api/jobs?lens=&sort=` route stays** as the HTTP contract (M2/external + tests); the Jobs
  view itself uses the shared logic client-side, not that HTTP route.
- **Drawer**: opening a row sets client `selected` state → renders `<JobDrawer job={selected}>` (the
  job is already in the pool). Close clears it.

Initial client state is `lens="all"`, `sort="match"` — deterministic, so the RSC server-render of
`<JobsView>` and the client hydration match (no hydration mismatch).

---

## 4. Jobs view (prototype §7.1 / `jobs.jsx:270–407`)

Ported to Tailwind-native components matching `views.css` (`.lens-bar`/`.lens`/`.toolbar`/`.colhead`/
`.jrow`/`.jline*`/`.deadline-banner`/`.empty`) + `specula.css` (`.vhead`/`.vtitle`/`.vsub`/`.vhead-stat`).

- **View header**: serif "Jobs" title + the `.vsub` explainer (the "location factor re-scores per
  lens" copy, verbatim); right-side `.vhead-stat` — `<b>{pool.length}</b> in pool · <b>{new}</b> new`
  (derived).
- **Lens bar** (`<LensBar>`): one `.lens` cell per lens — `l.short` + a green `.lens-newdot` when that
  lens has new roles, and a mono `{count} roles · {new} new` line, both **derived** from
  `filterByLens(pool, l.id)`. Active cell = ink fill. Click → client `setLens`.
- **Deadline banner**: shown when `≥1` role in the current lens closes within 7 days (`deadlineDays
  <= 7`, excluding already-`Applied`), warn-tinted (`.deadline-banner`), verbatim copy.
- **Toolbar**: the active lens's `scope · modes.join(" / ") · origin`, plus "◉ match re-scored for
  this lens" when `lens !== "all"`; and a sort `<select>` (match index ↓ / deadline ↑ / newest) →
  client `setSort`.
- **Column header** (`.colhead`): `# · role / source / facts · match · role / skill / loc`.
- **List** (`.jlist`): `JobRow` per job; the empty state (`.empty`, "No roles in this lens yet…") when
  the filtered list is empty.

## 4.1 JobRow (`jobs.jsx:14–56`)

The `.jrow` 3-col grid (`.jidx` zero-padded index / `.jbody` / `<MatchMeter>` — style from the M1c
Tweaks default `"bars"`, hard-coded `"bars"` in M1b since the Tweaks panel is M1d):
- `.jline1`: `.jtitle` (serif) + `<Tag variant="new">NEW</Tag>` when `isNew` + `<Tag variant="status">`
  when `status && status !== "Dismissed"`.
- `.jline2`: company (`.jco` + `.jco-logo`), `/ {flag} {city}`, `/ {mode}` (unless city includes
  "Remote"), `/ {seniority}`, `/ {salary}` (only when present — salary display-only).
- `.jrat`: the rationale paragraph.
- `.jline3`: `<OverlapBar overlap={job.overlap} />`, the top-5 `stack.slice(0,5).join(" · ")`, `↳
  closes {deadlineDays}d` (`.soon` warn when `<= 7`), `⚑ {redFlag}` when present, `⚐ origin
  unverified` when `!originVerified`.
- Click anywhere on the row → open the drawer for that job. (In M1b, no rect capture — the row→drawer
  **morph** is M1c; M1b just opens the drawer.)

---

## 5. Drawer (prototype §7.2 / `jobs.jsx:129–268`)

A client right-side panel (`.drawer`, 560px, `--shadow-pop`) over a blurred `.scrim`. **M1b: plain
slide-in** (`translateX(100%)→0`, the prototype's non-morph path) — the row→drawer **morph** and the
MatchMeter **scoring reveal** are **M1c** (here MatchMeter renders its final value, no `reveal`).
Close via ✕ / scrim click / **Esc**; unmount on close (a simple slide-out is fine; the fancy
onfinish+fallback choreography is M1c).

Sticky `.dr-head`: kicker (`.jco-logo` + company + `flag city · mode` + NEW tag), serif `.dr-title`,
`.dr-sub` (seniority · contract · mono "posted …"). Body `.dr-body` sections, each under a mono
`.dr-sec-h`:
1. **Match** — `<MatchMeter mstyle="bars">` (final value) + rationale + `<OverlapBar>` + "↳ closes in
   N days".
2. **Summary** — `.dr-summary` paragraph.
3. **Skills · required vs your profile** — header shows "{overlap[0]} of {overlap[1]} matched"; body
   = have `.sg.have` (✓, accent) + missing `.sg.miss` (+, warn dashed), split by `candidateHas`
   (§6); the amber-gaps note when any missing.
4. **Insight record** — `<dl class="kv">` of the 14 extracted fields (`jobs.jsx:58–85` — role family,
   seniority, experience, education, work mode, location, geo, visa, languages, salary|"not stated in
   ad", contract, deadline, posted, still-open), ending with **extraction confidence** → `.lowconf`
   (warn) + " — surfaced, not trusted" when `confidence < 75`.
5. **Responsibilities** — bullet list.
6. **Application status** — the 4-step `Lifecycle` (Saved→Applied→Interviewing→Offer) **displaying**
   the job's current status (done/active steps); the note textarea shows the seed note. **Inert in
   M1b** (clicking a step / editing the note does not persist — M2).
7. **Feedback** — the ↑ Good / ↓ Not-for-me controls render in their default state; **inert in M1b**
   (the like/dismiss/reason flow + row removal is M2).
8. **Footer** — "↗ Open posting" (`btn-pri`) + "★ Save" (`btn`); **inert in M1b** (M2).

> The mutating controls (6–8) are rendered at full visual fidelity for the pixel-port + M1d visual-
> regression, but do nothing in M1b — M2 wires them to the API. This keeps M1b-1 a clean static render
> and avoids building throwaway local-only state that M2 would rewrite.

---

## 6. Skill matching (`lib/api` or `components/jobs/skills.ts`)

Port `candidateHas` (`jobs.jsx:8–12`) verbatim: lowercase the candidate skills and the target; a skill
is "had" if any candidate skill equals it, contains it, or the target's first word is contained. The
Skills section splits the job's required skills (`job.stack`) into `have`/`miss` with it. Pure +
unit-tested.

---

## 7. Testing

Views are behind the M0b auth guard, so they **cannot be E2E'd cred-free** (the unauth→/signin
redirect is already covered). M1b-1 is tested by **Vitest component tests** against seed props:
- **Data-access:** `getJobsPool`/`getJobs`/`getLenses`/`getCandidate` return the right typed data;
  `getJobs("foreign","match")` filters+scores+sorts+derives (reuses the M1a assertions); the
  refactored `/api/*` routes still return the same shapes.
- **`candidateHas` / skills split:** known candidate vs a job's stack → correct have/missing.
- **`LensBar`:** renders derived counts (e.g. All "13 roles · 7 new", not 47/11); active lens marked.
- **`JobRow`:** renders title + NEW/status tags + meta (company/city/mode/seniority/salary-when-present)
  + rationale + OverlapBar + stack + deadline (`.soon` when ≤7) + red-flag/origin-unverified flags;
  clicking calls the open handler.
- **`JobsView`:** derived pool/new header counts; deadline banner appears when a role closes ≤7d;
  switching lens (client) re-filters + re-scores (loc/match change, role/skill constant) and updates
  counts; empty state when a lens has no roles.
- **`JobDrawer`:** renders all 8 sections for a job; skills have/missing split; **extraction-confidence
  warn + "surfaced, not trusted" when confidence < 75** (use the red-flag seed job j5, confidence 79 —
  or assert a <75 case); salary shows "not stated in ad" when null; Esc/close clears selection.
- **Gates:** `just lint/typecheck/test` + `pnpm build` + `pre-commit` green; CI green.

---

## 8. Acceptance (M1b-1 definition of done)

1. `/jobs` (when authed) renders the editorial Jobs view against the seed: header with derived
   pool/new counts, the lens bar with **derived** per-lens counts, deadline banner, toolbar (lens
   rules + sort), column header, and the 13-job list with MatchMeter + full meta/footer per row.
2. Switching a lens (client) re-filters and **re-scores** the pool (loc factor + overall match change;
   role/skill constant) and re-derives the counts; sort (match/deadline/newest) reorders. No FLIP
   animation yet (M1c).
3. Clicking a row opens the Drawer for that job (plain slide-in) showing all 8 sections from the
   insight record; extraction confidence renders "surfaced, not trusted" when < 75; skills split into
   have/missing; salary is display-only. Esc / ✕ / scrim closes it.
4. The mutating controls (status, feedback, save, note) render at full fidelity but are inert (M2).
5. The `lib/api` data-access layer exists; the M1a `/api/*` routes are refactored to use it (DRY) and
   still return the same shapes; component + data-access Vitest tests pass.
6. `just lint && just typecheck && just test` + `pnpm build` + `pre-commit run --all-files` green; CI
   (api + web) green. No new E2E (auth-gated views; unauth redirect already covered).

---

## 9. Open considerations for the plan

- **MatchMeter style in M1b:** hard-code `mstyle="bars"` (the Tweaks default). The Tweaks panel that
  lets it change is M1d; wiring per-user style is deferred.
- **Drawer mount/animation:** a plain CSS/`translateX` slide-in is enough for M1b; do NOT build the
  morph/reveal/onfinish-fallback (M1c). Keep the drawer a client component so M1c can add them.
- **`/api` route refactor scope:** refactor `/api/jobs`, `/api/jobs/[id]`, `/api/lenses`,
  `/api/candidate` to the data-access layer now (they're the ones M1b-1 touches); M1b-2/3 do the rest
  (companies/approvals/insights/targeting) when those views land.
- Everything else is specified; no TBDs.
