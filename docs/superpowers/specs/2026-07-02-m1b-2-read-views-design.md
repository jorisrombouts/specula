# Specula M1b-2 — Read views (Approvals · Companies · Insights): Design Spec

> **Status:** approved design, ready for `writing-plans`.
> **Milestone:** M1b-2 — the second of three M1b sub-pieces (M1b = "static views"). Decomposition:
> M1b-1 Jobs + Drawer ✅ → **M1b-2 Approvals + Companies + Insights** → M1b-3 Profiles + Candidate +
> Targeting. Inherits every architectural decision M1b-1 settled (RSC page → `lib/api/` data-access →
> client view; derived counts; static; inert persisting-interactivity).
> **Sources of truth:** prototype `prototype/specula/pipeline.jsx` (Approvals + Companies),
> `prototype/specula/intel.jsx` (Insights), `views.css` + `specula.css` (styling), prototype spec
> §7.3–§7.5, production spec §10, `CLAUDE.md`.
> **Conflict rule:** visuals → prototype wins; architecture/behavior → production spec wins.

---

## 1. Goal & boundary

Port the prototype's three **read views** — the Approval queue, the Companies registry, and the
Insights dashboard — to typed React against the M1a seed/atoms, **statically**: pixel-faithful,
real derived data. This completes the "everything-but-the-forms" half of M1b.

**In scope (M1b-2):**
1. **Data-access additions** (`lib/api/`): `getApprovals()`, `getCompanies()`, `getInsights()` server
   functions over the seed; the three remaining M1a stub routes (`/api/approvals`, `/api/companies`,
   `/api/insights`) refactored to call them (DRY — finishes the route-refactor M1b-1 started).
2. **Approval queue** (`(app)/approvals`): RSC page → client `<ApprovalsView>` with the 2-col card
   grid of `<ApprovalCard>`s (logo, name+flag, domain, "N open" chip, why, ATS + HQ / unverified flag,
   the "found via" query line, and the Approve/Reject/Snooze actions rendered **inert**). Empty state.
3. **Companies registry** (`(app)/companies`): RSC page → client `<CompaniesView>` with a **live**
   text-filter and the registry **table** (company, ATS, HQ, HQ-confidence bar, open, comp-est chip,
   tracking Toggle rendered **inert**). Header counts **derived**.
4. **Insights** (`(app)/insights`): RSC page → client `<InsightsView>` — the low-confidence exclusion
   banner + the six CSS-chart panels (**verbatim port of the prototype's hand-built charts**, not a
   dataviz redesign). Bars render at final width (grow/count-up → M1c). Period-select **inert**.
5. A small **`Chip` atom extension**: add an optional `strong` prop (prototype `.chip-strong` =
   `text-ink` + `border-rule-2`) for the Companies comp-est chip. Backward-compatible.

**Out of scope (deferred, with owner):**
- **Animations → M1c:** the Insights bar-grow / segmented-bar flex / `useCountUp` (analysed count,
  skill-demand widths, seniority/mode/salary/active-company bars), the approval-card "gone" exit, and
  any entrance stagger. In M1b-2 every bar/number renders at its **final** value.
- **Persisting/mutating interactivity → M2:** Approvals **Approve/Reject/Snooze** (mutate the queue +
  registry), the Companies **tracking Toggle** (persists tracking on/off), and the Insights
  **period-select** (would refetch aggregates). All render at full visual fidelity but are **inert**
  in M1b-2 (same rule as M1b-1's drawer controls). Consequence: the Approvals header shows the seed
  queue length + `0 approved` (no live session log — that arrives with M2's real actions).
- The other views → M1b-1 ✅ (Jobs+Drawer), M1b-3 (forms). Real API/DB → M2.

**Invariants honored** (`CLAUDE.md`):
- **Counts DERIVED, never hard-coded** — Companies `{companies.length} tracked` + `{Σ open} open
  roles` (summed server-side); Approvals `{approvals.length} pending`; the filter's "N of M". Never
  cosmetic constants.
- **Salary / comp display-only** — the Companies comp-est chip and the Insights salary-distribution
  panel are informational; they never rank, filter, or score. The salary panel keeps its "Never used
  to rank or filter" caption.
- **Low-confidence "surfaced, not trusted"** — Insights renders the "⚐ N low-confidence extractions
  excluded from every aggregate… treat trends as directional" banner; Companies flags HQ-confidence
  `< 80` with `⚐`. These are the invariant made visible.
- **Numbers computed, prose generated** — all chart values come from the seed's `Insights` numbers;
  the captions are fixed prose. The view never derives one from the other.

---

## 2. Files

```
apps/web/src/
  lib/api/
    approvals.ts        # CREATE — getApprovals(): Approval[]
    companies.ts        # CREATE — getCompanies(): Company[]
    insights.ts         # CREATE — getInsights(): Insights
  app/api/approvals/route.ts     # MODIFY — call getApprovals() (DRY)
  app/api/companies/route.ts     # MODIFY — call getCompanies()
  app/api/insights/route.ts      # MODIFY — call getInsights()
  components/atoms/chip.tsx       # MODIFY — add optional `strong` prop
  app/(app)/approvals/page.tsx    # MODIFY — RSC: getApprovals() → <ApprovalsView>
  app/(app)/companies/page.tsx    # MODIFY — RSC: getCompanies() → <CompaniesView>
  app/(app)/insights/page.tsx     # MODIFY — RSC: getInsights() → <InsightsView>
  components/approvals/
    approvals-view.tsx            # CREATE (client) — header + grid/empty
    approval-card.tsx             # CREATE — one card (actions inert)
  components/companies/
    companies-view.tsx            # CREATE (client) — header + live filter + table
  components/insights/
    insights-view.tsx             # CREATE (client) — header + banner + 6 panels
    demand-trend.tsx              # CREATE — the stacked weekly chart (its own file — reused shape)
  components/{approvals,companies,insights}/*.test.tsx   # CREATE — Vitest component tests
  lib/api/*.test.ts                                      # CREATE — data-access tests
```

Rationale for the split: mirror M1b-1 (`components/<view>/`). `ApprovalCard` and `DemandTrend` are
their own files (a card is reused across the grid; the trend chart is a self-contained sub-chart).
`CompaniesView` and `InsightsView` are single files each — the table and the 6 panels are cohesive.

---

## 3. Data flow (identical to M1b-1)

- **`lib/api/` functions** wrap the seed: `getApprovals(): Approval[]`, `getCompanies(): Company[]`,
  `getInsights(): Insights`. The three `/api/*` routes are refactored to call them (behavior-
  preserving — same JSON). M2 swaps the bodies to BFF→FastAPI.
- **Each RSC page** calls its data-access function and passes the result to the client view. Fast SSR
  first paint; no HTTP round-trip.
- **Client views** hold only **ephemeral view-state**: `CompaniesView` holds the filter string
  (client-side row filtering, exactly like M1b-1's lens/sort). `ApprovalsView` and `InsightsView` hold
  no persisted state in M1b-2 (their stateful controls are inert). Initial state is deterministic
  (empty filter, default period) → hydration-safe.

---

## 4. Approval queue (prototype §7.3 / `pipeline.jsx:5–61`)

Ported to Tailwind matching `views.css` `.appr*`.

- **Header** (`.vhead`): "Approval queue" + the `.vsub` explainer (verbatim); right `.vhead-stat` —
  `<b>{approvals.length}</b> pending` · `<b>0</b> approved` (no live log in M1b-2 — actions inert).
- **Grid** (`.appr-grid`, 2-col): an `<ApprovalCard>` per approval, keyed by `c.id`.
- **`<ApprovalCard>`** (`.appr`): `.appr-top` (`.appr-logo`, `.appr-name` + flag, `.appr-dom`, right
  `<Chip mono>{c.roles} open</Chip>`); `.appr-why` rationale; `.appr-meta` (`.ats` ATS badge, and
  either `<Chip mono>HQ {c.hq}</Chip>` or `<Tag variant="flag">⚐ HQ origin unverified</Tag>` when
  `c.unverified`); `.appr-q` "⌕ found via '{c.query}'"; `.appr-acts` — **Approve** (`Button
  variant="accent"`), **Reject** (`Button`), **Snooze** (`Button`, "☾"). The three action buttons
  render at full fidelity but are **inert** (no onClick) — M2 wires decide().
- **Empty state** (`.empty`): only reachable in M2 (the seed queue is non-empty); still ported for
  completeness — "Queue clear…" with the ✓ icon.

## 5. Companies registry (prototype §7.4 / `pipeline.jsx:63–117`)

Ported to Tailwind matching `views.css` `.tbl*`/`.conf*` + `.toolbar`.

- **Header**: "Companies" + `.vsub`; right stat — `<b>{companies.length}</b> tracked` ·
  `<b>{totalOpen}</b> open roles` where `totalOpen = companies.reduce((s,c)=>s+c.open, 0)` (**derived**,
  computed in the client view from the passed list).
- **Toolbar**: a text `<input>` (the `.input` style, max-width ~280) — **LIVE**: filters rows where
  name or HQ contains the query (case-insensitive), exactly the prototype's predicate; and a mono
  `{rows.length} of {companies.length}` count that updates with the filter.
- **Table** (`.tbl`): head `Company · ATS feed · HQ country · HQ confidence · Open · Comp est. ·
  Tracking`. Each row (`key={c.name}`): `.tbl-co` (logo + name + `.tbl-dom` domain); `.ats` badge;
  `{c.flag} {c.hq}`; **HQ confidence** `.conf` (a `.conf-track` bar at `c.conf%` + `{c.conf}%`, with
  `.low` warn styling + " ⚐" suffix when `c.conf < 80`); `{c.open}` mono; `<Chip strong>{c.comp}</Chip>`
  (comp-est — **display-only**); and a **tracking `<Toggle>`** rendered `on` but **inert** (no
  onChange) — M2 wires it.

## 6. Insights (prototype §7.5 / `intel.jsx:5–133`)

**Verbatim port of the prototype's hand-built CSS charts** (they are the design — not a `dataviz`-skill
redesign). Ported to Tailwind matching `views.css` `.ins-grid`/`.panel*`/`.demand*`/`.trend*`/`.mixbar`/
`.salary-rows`/`.sal-*`/`.legend`.

- **Header**: "Insights" + `.vsub` (which itself states low-confidence extractions are excluded);
  right — a period `<select>` (default "Last 8 weeks", **inert** → M2) + `<b>{totalAnalysed}</b>
  analysed` (final value; the count-up is M1c).
- **Low-confidence banner** (`.appr-why`): "⚐ {lowConfExcluded} low-confidence extractions excluded
  from every aggregate below. Treat trends as directional." — the "surfaced, not trusted" invariant.
- **Six panels** (`.ins-grid`, each `.panel` with a `.panel-h` title + sublabel):
  1. **Skill demand** — a `.demand-row` per `skillDemand` entry: `.demand-k` name (+ a "gap"
     `Tag variant="flag"` when `s.gap`), a `.demand-track` bar at `s.pct%` (`.up` accent when
     `s.up`), and `.demand-d` Δ (`▲/▼ |delta|%`, up/down colored). **Final width (no grow).**
  2. **Demand drift** — `<DemandTrend trend={insights.trend}>`: for each week, a `.trend-stack` of
     `.trend-seg`s (one per series, `background: series.color`, `height = data[wi]/max*130px`), a
     `.trend-x` week label, and a `.legend` of the series. `max = Σ per-week totals` (computed).
  3. **Seniority mix** — `.demand-row` per `seniorityMix`: bar at `v/seniorMax*100%`, accent when
     `k === "Senior"` else ink; `.demand-d` `{v}%`. `seniorMax = max(v)`.
  4. **Work-mode mix** — a `.mixbar` of segments (`flex: m.v`, `background: m.color`, label `{v}%`) +
     a `.legend` + the "Remote share is up +5pts…" caption (verbatim).
  5. **Salary distribution** — a `.sal-row` per band: a mono `{band}` label + a `.sal-bar` with the
     inner span positioned `left: lo%`, `width: (hi-lo)%`; + the "Only ~38% of ads list pay. Never
     used to rank or filter…" caption (**salary invariant**).
  6. **Most-active companies** — `.demand-row` per `activeCompanies`: bar at `n/12*100%` (accent for
     the top entry, index 0), `.demand-d` `{n}`.

> All six panels render at final values in M1b-2. The `run`-gated grow animations and the
> `useCountUp` in the prototype are **M1c**; the components should be structured so M1c can add a
> `run` flag without restructuring (e.g. width comes from a value the component computes, not a magic
> literal).

---

## 7. Chip atom extension (`components/atoms/chip.tsx`)

Add an optional `strong?: boolean` prop. When set, the chip uses the prototype `.chip-strong` styling
(`text-ink` + `border-rule-2`) instead of the default (`text-ink-2` + `border-rule`). `mono` and
`strong` compose. Backward-compatible — existing `<Chip>` / `<Chip mono>` usages unchanged. A test
asserts the `strong` variant renders the stronger classes.

---

## 8. Testing

Views are auth-gated → **no new E2E** (the unauth redirect is already covered). M1b-2 is tested by
**data-access unit tests + Vitest component tests** against seed props:
- **Data-access:** `getApprovals`/`getCompanies`/`getInsights` return the seed data; the three
  refactored routes still return the same shapes.
- **`Chip` strong variant:** renders the `text-ink`/`border-rule-2` classes; default + `mono`
  unchanged.
- **ApprovalCard / ApprovalsView:** a card renders name/domain/why/roles-chip/ATS/query; the
  unverified flag shows for an unverified approval and the `HQ {hq}` chip for a verified one; the
  header shows the **derived** pending count; the action buttons render (and are inert — no handler
  wired).
- **CompaniesView:** header shows **derived** `{n} tracked` + **derived** `{Σ open} open roles`; a row
  renders logo/name/domain/ATS/HQ/open/comp-chip/toggle; **HQ-confidence `< 80` shows the `.low` warn
  styling + ⚐**, `≥ 80` plain; typing in the filter narrows the rows and updates the "N of M" count
  (case-insensitive, matches name AND HQ).
- **InsightsView / DemandTrend:** the low-confidence banner shows `{lowConfExcluded}`; the six panels
  render (skill-demand rows incl. a "gap" tag, the trend segments per week, seniority/mode/salary/
  active-company rows); the salary caption's "Never used to rank or filter" text is present; the
  `analysed` number shows `totalAnalysed`.
- **Gates:** `just lint/typecheck/test` + `pnpm build` + `pre-commit` green; CI green.

---

## 9. Acceptance (M1b-2 definition of done)

1. `/approvals` (authed) renders the editorial Approval queue against the seed: header with derived
   pending count, the 2-col card grid with all card fields, and inert Approve/Reject/Snooze actions.
2. `/companies` renders the registry table with derived `tracked` + `open roles` counts, the HQ-
   confidence bar (⚐ warn when `<80`), the comp-est chip (display-only), and an inert tracking toggle;
   the text-filter narrows rows + updates the "N of M" count live.
3. `/insights` renders the low-confidence exclusion banner + the six CSS-chart panels at their final
   values, including the salary "never used to rank or filter" caption; the period-select is inert.
4. The `lib/api` data-access layer gains `getApprovals`/`getCompanies`/`getInsights`; the three
   `/api/*` routes are refactored to use them (DRY) and still return the same shapes.
5. The `Chip` atom gains a backward-compatible `strong` variant.
6. No animations (M1c) and no persisting mutations (M2) are wired; deferred controls render inert.
7. `just lint && just typecheck && just test` + `pnpm build` + `pre-commit run --all-files` green; CI
   (api + web) green. No new E2E.

---

## 10. Open considerations for the plan

- **Insights panel structure for M1c-readiness:** compute each bar's width from a value in the
  component (not a literal) so M1c can gate it behind a `run` flag without restructuring. Do NOT add
  the animation now.
- **`totalOpen` derivation:** compute in the client `CompaniesView` from the passed `companies` list
  (`reduce`) — keeps the "derived, never stored" invariant and matches the prototype.
- **Inert controls:** render the action buttons / toggle / period-select at full fidelity with NO
  handlers (no local mutation state) — M2 owns wiring. Same decision as M1b-1's drawer controls.
- **Route-refactor scope:** the three routes M1b-2 touches (`approvals`/`companies`/`insights`)
  complete the `/api` → `lib/api` migration begun in M1b-1. No routes remain after this.
- Everything else is specified; no TBDs.
