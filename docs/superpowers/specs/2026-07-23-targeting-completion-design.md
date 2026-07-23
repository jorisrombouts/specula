# Targeting page completion — design

**Date:** 2026-07-23 · **Milestone:** M6 (Polish & launch) · **Status:** approved for planning

## Problem

The `/targeting` ("Targeting") page is display-only in practice — nothing you
change is saved, and one field can't be edited at all.

| Element | Current UI | Issue |
|---|---|---|
| Role titles, Must-haves, Avoid | `TagEditor` (local state) | editable, but **never persisted** |
| Seniority | renders read-only chips | **not editable** |
| Preferences | uncontrolled `defaultValue` textarea | **not in state, never persisted** |
| Persistence | none — no Save button, no BFF `PUT` route, no `saveTargeting` | **every edit is lost on reload** |

The backend is already complete: FastAPI exposes `GET`/`PUT /targeting`
(`replace_targeting` → `upsert_targeting`, a full replace), and the `targeting`
table stores `role_titles`, `seniority`, `must_haves`, `avoid` (all `text[]`) and
`preferences` (`text`). `upsert_targeting` re-embeds nothing (targeting has no
vector column). So this is a **frontend-completion job** — no schema or endpoint
change.

## Goal

Make `/targeting` fully editable and persistent, and fold in two improvements:

1. Wire persistence (client `saveTargeting` + BFF `PUT` route) with a dirty-state
   save, mirroring the candidate page.
2. Make **seniority** an editable multi-select over a canonical ladder.
3. Control the **preferences** textarea (state, not `defaultValue`).
4. Add a **suggestions** typeahead to **role titles** (common-titles catalog).

Reuse everything built for the candidate page: the dirty-state save pattern, the
`TagEditor` `suggestions` prop, and (generalized) the `ModeSelect` chip toggles.

## Non-goals (explicitly out of scope)

- **No geography or salary** on this page — spec invariant (targeting holds no
  location/work-mode/HQ rules; those live in Search profiles/lenses). Salary is
  never a rule or signal.
- **No backend seniority enum.** Seniority is constrained on the frontend only
  (see "Backend" below); the API keeps `seniority: list[str]`.
- No discovery-seed preview, no new scoring behavior, no schema/endpoint change.

## Product constraints carried in from the spec

- Targeting is the **global baseline** — role identity, seniority, values —
  shared across every lens; drives discovery and the **role & skill match
  factors** (spec §4.2).
- `role_titles` + `seniority` feed the **role factor** (cosine of a posting's
  `title_vec` vs the user's role titles, adjusted for **seniority match**);
  `must_haves` trigger a **red-flag penalty** when absent; `preferences` is a
  **soft LLM signal**. So seniority is a real scoring input — worth constraining
  to canonical values.

---

## Field specification

### Role titles — tag editor + suggestions
- Keeps the `TagEditor` (`kind="syn"`) chip model, plus a `<datalist>` typeahead
  over a bundled common-titles catalog, with free-add preserved. Frontend-only;
  no schema change. `role_titles` stays `string[]`.

### Seniority — multi-select `Seniority[]`
- Chip-toggles (the generalized `ChipMultiSelect`) over the ladder:
  `Junior · Mid · Senior · Staff · Principal · Lead · Manager · Director`.
- Type change: `Targeting.seniority: string[]` → `Seniority[]`.
- `getTargeting` **sanitizes** the read: any stored value outside the ladder is
  dropped (filtered to `SENIORITY_LEVELS`), so the component always gets valid
  values and a legacy value simply disappears for the user to re-pick — the same
  read-sanitization approach used on the candidate page. (Backend read stays
  lenient `list[str]`, so `GET /targeting` never 500s on a legacy value.)
- Seed `["Mid", "Senior", "Staff"]` is already valid; no seed change needed.

### Must-haves / Avoid — unchanged editors, now persisted
- `TagEditor` (Avoid uses `kind="avoid"`), stay `string[]`. Now saved.

### Preferences — controlled textarea
- Move from uncontrolled `defaultValue` to `value`/`onChange` state so edits are
  tracked and saved. Stays `string`.

---

## Persistence + save UX

- **Client:** add `saveTargeting(patch)` to `lib/api/targeting.ts` (PUTs to the
  BFF route), and a `getTargeting` mapping that sanitizes seniority.
- **BFF route:** add a `PUT` handler to `app/api/targeting/route.ts` that proxies
  to FastAPI `PUT /targeting` (mirrors the candidate route).
- **Dirty-state save** (reuse the candidate-view pattern): compare current form
  to the last-saved baseline (`JSON.stringify`). "Save targeting" is **disabled
  when clean**; an "Unsaved changes" hint shows when dirty; a "Saved."
  confirmation shows after a successful save; the baseline updates on save. **No
  autosave** (save re-embeds nothing — cheap — but explicit save is simpler and
  consistent).

---

## Components

- **`ChipMultiSelect<T extends string>`** (new, in `components/atoms/`) —
  generalize the candidate `ModeSelect` into a reusable
  `{ options: readonly T[]; value: T[]; onChange: (v: T[]) => void }` chip-toggle
  (renders each option, `aria-pressed` reflects selection, click toggles it
  in/out of `value`).
  - **`ModeSelect` is refactored to delegate** to it
    (`<ChipMultiSelect<Mode> options={WORK_MODES} … />`) — single consumer
    (candidate-view), and `mode-select.test.tsx` guards the refactor.
  - **Seniority** uses `<ChipMultiSelect<Seniority> options={SENIORITY_LEVELS} … />`.
- **`TagEditor` suggestions** — reuse the existing `suggestions?` prop; pass
  `ROLE_TITLES` for role titles.
- Dirty-state save markup — reuse the candidate-view pattern.

`targeting-view.tsx` is rewritten to own form state, the dirty flag, the seniority
multi-select, the controlled preferences textarea, role-title suggestions, and the
save handler.

---

## Backend

**No schema, model, endpoint, or service change.** `GET`/`PUT /targeting`,
`TargetingIn`/`TargetingOut`, the `targeting` table, and `upsert_targeting` are
untouched. `seniority` stays `list[str]` server-side.

**Seniority validation is frontend-only** (the multi-select constrains input by
construction). Rationale: adding a strict `Literal` to `TargetingIn`/`Out` would
reintroduce the read-500 bug class fixed on the candidate page — a legacy /
out-of-ladder stored value would make `GET /targeting` raise a `ValidationError`
(500) unless we also split `In`/`Out` for read-leniency. Seniority match is fuzzy,
so the payoff is low. The frontend read-sanitization (above) already normalizes
what the UI shows.

---

## Constants / catalogs

- `Seniority` type + `SENIORITY_LEVELS` (the 8-level ladder) →
  `packages/shared-types/src/index.ts` (like `WORK_MODES`). `Targeting.seniority`
  changes to `Seniority[]`.
- `ROLE_TITLES` common-titles catalog →
  `apps/web/src/lib/role-titles-catalog.ts` (web-only, like `skills-catalog.ts`).

---

## Testing (TDD)

- **`ChipMultiSelect`** component test: renders options, `aria-pressed` reflects
  `value`, clicking an off option adds it / an on option removes it.
- **`ModeSelect`** existing test still passes (guards the delegation refactor).
- **`targeting-view`** tests: dirty-state gates the Save button; toggling a
  seniority level updates state and marks dirty; a role-title added via the
  suggestions input (free-add) appears; editing preferences marks dirty; "Save
  targeting" PUTs the edited fields through the BFF route.
- No new API tests — the backend is unchanged; existing targeting API tests still
  pass.

## Files touched (indicative)

- `packages/shared-types/src/index.ts` (`Seniority`, `SENIORITY_LEVELS`;
  `Targeting.seniority` → `Seniority[]`)
- `apps/web/src/lib/role-titles-catalog.ts` (new)
- `apps/web/src/components/atoms/chip-multi-select.tsx` (+ test, new)
- `apps/web/src/components/candidate/mode-select.tsx` (refactor to delegate)
- `apps/web/src/lib/api/targeting.ts` (`TargetingApiOut`, sanitizing `getTargeting`,
  new `saveTargeting`)
- `apps/web/src/app/api/targeting/route.ts` (add `PUT`)
- `apps/web/src/components/targeting/targeting-view.tsx` (rewrite)
- `apps/web/src/components/targeting/targeting-view.test.tsx` (update)
