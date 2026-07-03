# Specula M1b-3 — Config forms (Profiles · Candidate · Targeting): Design Spec

> **Status:** proposed design (written on best-judgment while awaiting review), ready for user review
> → then `writing-plans`.
> **Milestone:** M1b-3 — the last of three M1b sub-pieces (M1b = "static views"). Decomposition:
> M1b-1 Jobs + Drawer ✅ → M1b-2 Approvals + Companies + Insights ✅ → **M1b-3 Search profiles +
> Candidate + Targeting**. Completes M1b; next is M1c (animations) then M1d (Tweaks + visual-
> regression). Inherits every architectural decision M1b-1/M1b-2 settled.
> **Sources of truth:** prototype `prototype/specula/config.jsx`, `views.css` + `specula.css`
> (styling), prototype spec §7.6–§7.8, production spec §10, `CLAUDE.md`.
> **Conflict rule:** visuals → prototype wins; architecture/behavior → production spec wins.

---

## 1. Goal & boundary

Port the prototype's three **config/edit views** — Search profiles (lenses), Candidate profile, and
Targeting — to typed React against the M1a seed/atoms. These are the app's **edit surfaces**, so
(unlike the read views) their in-view editing is **live client-local state** — the exact shape M2
converts to persistence. This completes the static M1b port.

**In scope (M1b-3):**
1. **Data-access additions** (`lib/api/`): `getTargeting()` (+ refactor `/api/targeting` route to it),
   `getSkillsGap()` (view-only, no route). **Reuse** `getCandidate()` + `getLenses()` (both from
   M1b-1 — `LensSummary` already carries the per-lens count/isNew + scope/modes/origin/focus/seeds/
   active the Profiles cards need).
2. **Search profiles** (`(app)/profiles`): RSC page → client `<ProfilesView>` — header (derived
   active/total), lens cards (derived counts, live active Toggle, hard-rules grid, focus + seeds),
   inert "+ New profile".
3. **Candidate profile** (`(app)/candidate`): RSC page → client `<CandidateView>` — header avatar
   (seed initials), the form (text inputs + a live Skills `TagEditor` + read-only Projects/Experience/
   Education/Languages), and the sticky Skills-gap panel (inert "Draft CV bullet").
4. **Targeting** (`(app)/targeting`): RSC page → client `<TargetingView>` — role-titles/must-haves/
   avoid `TagEditor`s (live), seniority read-only chips, a preferences textarea, and the accent info
   banner (the geography + salary invariants made visible).

**Interactivity — LIVE client-local (the M2 shape), NOT persisted:**
- The `TagEditor` add/remove (Skills, Role titles, Must-haves, Avoid) and the lens active `Toggle`
  work **client-side**: each view holds `useState(seedValues)` and passes `values`/`onChange` to the
  atom. Edits update the local state and **reset on reload** — no persistence. Text inputs + the
  preferences textarea are **uncontrolled** (`defaultValue`, typeable-local). This is the prototype's
  exact behavior and the exact structure M2 needs: swap `useState` → a persisting mutation hook, no
  rework.
- **Deliberate deviation from M1b-2:** the lens active-Toggle is LIVE here, whereas M1b-2's Companies
  tracking-Toggle is inert. Rationale: these are *edit views* (editing is their purpose + the M2
  shape), vs Companies being a *read view* where the toggle is incidental. Both are internally
  consistent with "M1b builds no throwaway state" because the config-view `useState` IS the M2
  structure (a trivial state holder), whereas wiring a read-view's per-row persistence early would be
  throwaway.

**Out of scope (deferred, with owner):**
- **Persistence → M2:** none of the live edits persist; the backend-action buttons ("+ New profile",
  "✎ Draft a tailored CV bullet") render at full fidelity but are **inert** (they need real backend
  actions). M2 wires all persistence + these actions.
- **Animations → M1c** (any entrance stagger; none of these views animate in the prototype beyond the
  shared `viewIn`, which is M1c).
- Real API/DB → M2. The other views → M1b-1/M1b-2 ✅.

**Invariants honored** (`CLAUDE.md`):
- **Counts DERIVED** — Profiles header `{active}/{total}` from the lenses; each lens card's
  `N roles · M new` from `LensSummary.count`/`.isNew` (derived over the pool). Never hard-coded.
- **Salary never a rule/signal; geography lives in profiles** — the Targeting info banner states both
  verbatim; Targeting deliberately has NO geography/mode fields (those are Search-profile rules).
- **Numbers computed, prose generated** — skills-gap `roles` counts + lens counts are data; the notes/
  copy are fixed prose.

---

## 2. Files

```
apps/web/src/
  lib/api/
    targeting.ts         # CREATE — getTargeting(): Targeting
    skills-gap.ts        # CREATE — getSkillsGap(): SkillsGap[]  (view-only, no route)
  app/api/targeting/route.ts        # MODIFY — call getTargeting() (DRY)
  app/(app)/profiles/page.tsx       # MODIFY — RSC: getLenses() → <ProfilesView>
  app/(app)/candidate/page.tsx      # MODIFY — RSC: getCandidate() + getSkillsGap() → <CandidateView>
  app/(app)/targeting/page.tsx      # MODIFY — RSC: getTargeting() → <TargetingView>
  components/profiles/profiles-view.tsx    # CREATE (client) — header + lens cards
  components/candidate/candidate-view.tsx  # CREATE (client) — header + form + skills-gap panel
  components/targeting/targeting-view.tsx  # CREATE (client) — header + tag fields + banner
  components/{profiles,candidate,targeting}/*.test.tsx   # CREATE — Vitest component tests
  lib/api/config.test.ts                                 # CREATE — data-access tests
```

Rationale: mirror the established `components/<view>/` layout. Each view is a single cohesive client
component (they share the `TagEditor`/`Toggle`/`Chip` atoms; no further sub-splitting needed).

---

## 3. Data flow (identical to M1b-1's JobsView pattern)

- **`lib/api/`** gains `getTargeting(): Targeting` and `getSkillsGap(): SkillsGap[]` over the seed.
  `/api/targeting` is refactored to call `getTargeting()` (behavior-preserving). `getSkillsGap` has no
  route (only the Candidate view consumes it). `getCandidate`/`getLenses` are reused unchanged.
- **Each RSC page** fetches its data and passes it to the client view. **Each view is `"use client"`**
  because it holds the editable local state (lens toggles / skills / tag fields). Initial state seeds
  from the passed props → deterministic → hydration-safe.

---

## 4. Search profiles (prototype §7.6 / `config.jsx:24–67`)

Ported to Tailwind matching `views.css` `.lens-cards`/`.lcard*`/`.rule-*`/`.seeds`/`.seed` + `.toggle`.

- **Header** (`.vhead`): "Search profiles" + `.vsub` (verbatim); right stat —
  `<b>{active}</b> active` · `<b>{total}</b> total`, where `active`/`total` come from the lens state
  (`getLenses()`; total counts all 5 including "all").
- **Lens cards** (`.lens-cards`, one per lens **excluding "all"** → the 4 regional lenses): `.lcard`
  (`.off` when inactive) with `.lcard-top` (name, `.lcard-badge` = **derived** `{count} roles ·
  {isNew} new` from the `LensSummary`, and a live active `<Toggle>` right-aligned); `.lcard-rules`
  (3-col grid: Location scope · hard = `scope`; Work mode · hard = `modes.join(" / ")`; Origin rule ·
  hard = `origin`); and a 2-col row below (Focus · soft = `focus || "—"`; Discovery seeds · auto =
  `seeds` as `.seed` chips).
- **Live toggle:** the view holds `useState(lenses)`; toggling flips that lens's `active` locally
  (card gains/loses `.off` dimming). No persistence (M2).
- **"+ New profile"** `Button` — inert (M2).

## 5. Candidate profile (prototype §7.7 / `config.jsx:70–138`)

Ported to Tailwind matching `specula.css` `.me-av` + `views.css` `.form-grid`/`.field*`/`.input`/
`.tagchip`/`.taglist`/`.gap-panel`/`.gap-*`/`.panel*`.

- **Header**: "Candidate profile" + `.vsub`; right = the `.me-av` avatar (rounded dark square,
  `candidate.initials` in paper color, 40×40 in this view).
- **Form-grid** (`1fr 320px`): **left column** —
  - Headline `<input defaultValue={candidate.title}>`; then a 2-col grid of Location / Work mode /
    Years experience (`{years} years`) / Visa inputs (all uncontrolled `defaultValue`).
  - **Skills** — a live `<TagEditor values={skills} onChange={setSkills}>` (view holds
    `useState(candidate.skills)`).
  - **Projects** — read-only `.tagchip` block per project (`<b>{name}</b> — {note}`).
  - a 2-col grid: **Experience** (read-only chips: `<b>{role}</b> · {org} <mono>{period}</mono>`) and
    **Education & languages** (education chip + language chips).
- **right column** — the sticky **Skills-gap panel** (`getSkillsGap()`): a `.panel` titled "Skills gap
  · vs target roles" with the "Most-demanded skills…" note and a `.gap-item` per gap (`.gap-bar` mini
  bars, `.gap-k` skill, `.gap-c` note, `.gap-n` `{roles}×`), then the inert "✎ Draft a tailored CV
  bullet" `Button`.

## 6. Targeting (prototype §7.8 / `config.jsx:140–182`)

Ported to Tailwind matching `views.css` `.field*`/`.taglist`/`.tagchip`/`.textarea` + `.deadline-banner`
(accent-tinted variant).

- **Header**: "Targeting" + `.vsub` (verbatim, incl. "Geography and work mode live in Search
  profiles").
- **Body** (`max-w-[760px]`):
  - **Role titles · synonyms** — live `<TagEditor kind="syn" values={titles} onChange={setTitles}>`.
  - **Seniority** — read-only `.tagchip` chips (`targeting.seniority`).
  - a 2-col grid: **Must-haves** (live `<TagEditor values={must} onChange={setMust}>`) and **Avoid**
    (live `<TagEditor kind="avoid" values={avoid} onChange={setAvoid}>`).
  - **Free-text preferences** — `<textarea defaultValue={targeting.preferences}>` (uncontrolled).
  - the **info banner** — the accent-tinted variant (`bg-accent-bg`, `border-accent`,
    `text-accent-ink`): "ⓘ No geography here, by design — location, work mode and HQ-origin rules
    belong to **Search profiles** (lenses)… Salary is likewise never a rule or signal; it's shown only
    when an ad states it." (verbatim — surfaces the geography + salary invariants).

---

## 7. Testing

Views are auth-gated → **no new E2E** (the unauth redirect is already covered). M1b-3 is tested by
**data-access unit tests + Vitest component tests**:
- **Data-access:** `getTargeting`/`getSkillsGap` return the seed data; the refactored `/api/targeting`
  route still returns the same shape.
- **ProfilesView:** header shows **derived** active/total; renders 4 cards (excludes "all") with
  **derived** `N roles · M new` badges + the hard-rules; clicking a card's toggle flips its active
  state locally (card gains the dimmed/`.off` styling).
- **CandidateView:** renders the header avatar (seed initials), the text inputs with seed values, the
  Projects/Experience/Education/Languages read-only chips, and the Skills-gap panel (a gap item with
  its `{roles}×`); the Skills `TagEditor` **adds a tag locally** (type + Enter → new chip) and
  **removes one** (× → chip gone).
- **TargetingView:** renders the three `TagEditor`s (titles/must/avoid) + seniority chips + the info
  banner (assert the "never a rule or signal" text); a `TagEditor` add/remove works locally.
- **Gates:** `just lint/typecheck/test` + `pnpm build` + `pre-commit` green; CI green.

---

## 8. Acceptance (M1b-3 definition of done)

1. `/profiles` (authed) renders the editorial Search-profiles view: derived active/total, the 4 lens
   cards with derived counts + hard rules + seeds, and the active toggles flip locally.
2. `/candidate` renders the candidate form (seed values), the Skills `TagEditor` (add/remove locally),
   the read-only Projects/Experience/Education/Languages, and the sticky Skills-gap panel.
3. `/targeting` renders the three tag fields (add/remove locally), seniority chips, the preferences
   textarea, and the accent info banner with the geography + salary invariant copy.
4. `lib/api` gains `getTargeting` + `getSkillsGap`; `/api/targeting` is refactored to use `getTargeting`
   and still returns the same shape.
5. No persistence and no backend actions are wired ("+ New profile" / "Draft CV bullet" inert); no
   animations (M1c).
6. `just lint && just typecheck && just test` + `pnpm build` + `pre-commit run --all-files` green; CI
   (api + web) green. No new E2E.

---

## 9. Open considerations for the plan

- **Reuse over re-create:** ProfilesView uses `getLenses()` (M1b-1) — `LensSummary` already has
  `active`/`scope`/`modes`/`origin`/`focus`/`seeds`/`count`/`isNew`; no new lens data-access. Only
  `getTargeting`/`getSkillsGap` are new.
- **TagEditor is used as-built** (M1a): `{ values, onChange, kind }`, controlled. The view is the
  state holder — `useState` now, mutation hook in M2 (same call shape).
- **Text inputs stay uncontrolled** (`defaultValue`) — matches the prototype; typeable-local, no
  persistence, no controlled-input warning.
- **Inert buttons** render with no `onClick`. **Toggle** on the lens card is live (real `onChange`
  updating local state); the Companies-view toggle stays inert (M1b-2) — the deliberate read-vs-edit
  distinction in §1.
- Everything else is specified; no TBDs.
