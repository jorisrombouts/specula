# Search-profiles (lenses) page completion — design

**Date:** 2026-07-23 · **Milestone:** M6 (Polish & launch) · **Status:** approved for planning

## Problem

The `/profiles` ("Search profiles") page is display-only. `ProfilesView` renders
lens cards but **you cannot create, edit, or delete a lens**, and the active
toggle is local-only (not persisted). Concretely:

- The client (`lib/api/lenses.ts`) exposes only `getLenses()` — no create / update
  / delete.
- The BFF route (`app/api/lenses/route.ts`) has only `GET`.
- `ProfilesView` renders every field (scope, modes, origin, focus, seeds)
  **read-only**; the toggle mutates local state only; "+ New profile" does nothing.

The **backend is already complete**: FastAPI exposes `GET` / `POST` (create, 201)
/ `PATCH /{id}` (update) / `DELETE /{id}` (204, and 409 on the protected default
lens), with `LensCreate` / `LensUpdate` / `LensSummaryOut` schemas and
server-derived counts. So this is a **frontend-completion job** plus two small,
justified backend additions.

## Goal

Turn `/profiles` into a full lens manager:

1. Wire lens **CRUD** into the frontend (create / edit / delete / toggle-active,
   all persisted) with **inline-expand card editing**.
2. **Structured inputs**: modes multi-select, a constrained origin-rule picker, a
   structured scope input (type + predefined region/country lists), and an
   editable seeds tag editor.

Reuse `ChipMultiSelect` (modes), `TagEditor` (seeds), and the dirty-state save
pattern.

## Non-goals (explicitly out of scope)

- **Changing the scope→WHERE pipeline.** Scope stays a `text` column; the frontend
  serializes structured input to the format the existing parser already reads
  (2-letter → country, "City, CC" → city, else soft). Fully wiring lens-aware
  scope filtering (e.g. region→countries expansion so "EU" hard-filters) is a
  separate pipeline effort. **`Region` scope is "soft"** today and is labeled so.
- **Auto-generating seeds** (spec allows "auto-generated, editable"; we ship
  editable now, defer generation).
- No geography/salary moving between surfaces; counts stay derived (never stored).

## Product constraints carried in from the spec

- **Lenses own geography & work mode entirely** — location scope, allowed modes,
  HQ-origin rule (+ soft focus signal and discovery seeds), layered over the
  global Targeting baseline (spec §4.2). Switching a lens re-scopes/re-scores the
  Jobs view on location (§6.2).
- `count` / `isNew` are **DERIVED server-side per request** — never stored, never
  set client-side (product invariant §4.3).
- The **default ("All") lens** cannot be deleted (backend 409s).

---

## Interaction model — inline-expand cards

- Each lens is a **read-only card** with an **Edit** affordance and an **active
  toggle**. Editing expands the card in place: its rows become inputs, with a
  footer of **Save / Cancel / Delete**.
- **"+ New profile"** appends a fresh editable card (blank, `active: true`).
- **Active toggle** persists immediately via `PATCH { active }` (no full save).
- **Dirty-state** per editing card: Save disabled until changed; "Unsaved
  changes" hint; on Save the card returns to read-only showing the saved values.
  Cancel discards; Delete removes (with the default-lens guard, below).
- The **default lens is filtered out of the editable card list** (matching current
  behavior) — it still counts toward the active/total header. This requires the
  summary to expose `isDefault` (see Backend).

---

## Field specification

Each editable field, its input, and how it maps to the stored lens columns
(`scope text`, `modes text[]`, `origin_rule text`, `focus text`, `seeds text[]`,
`active bool`, `name text`, `short text`):

### Name — text
Required. `short` is **auto-set to `name`** on save (not a separate field; the
jobs lens-bar uses `short` as a compact label).

### Scope — structured `{ type, value }`, serialized to the `scope` text column
Type picker `Any / Region / Country / City` + a value control:
- **Any** → no value; serializes to `""` (no location filter).
- **Region** → **predefined dropdown** (`REGIONS`); serializes to the region name
  (e.g. `"EU"`). **Soft** today (no hard filter) — shown with a `soft` tag.
- **Country** → **predefined dropdown** (`COUNTRIES`, option value = 2-letter
  code, label = `"Name (CODE)"`); serializes to the code (e.g. `"ES"`). Hard
  filter.
- **City** → free text `"City, CC"` (e.g. `"Berlin, DE"`) — cities can't be
  enumerated. Hard filter.

**Round-trip (no schema change):** the client parses the stored `scope` text back
into `{ type, value }` via `parseScope`, checking the region catalog **first** so
a 2-letter region (e.g. `"EU"`) can't be mistaken for a country code:
- `""` → `{ Any }`
- value ∈ `REGIONS` (e.g. `"EU"`, `"Nordics"`) → `{ Region, value }`
- `/^[A-Z]{2}$/` (e.g. `"ES"`) → `{ Country, value }`
- otherwise (e.g. `"Berlin, DE"`, or any free text) → `{ City, value }`

Regions are always chosen from the dropdown, so a stored region is always in
`REGIONS` and round-trips exactly; legacy/free-text scope falls to `City`
best-effort.

### Work mode — `ChipMultiSelect` (Mode[])
Remote / Hybrid / On-site → `modes text[]`.

### Origin rule — select (label ↔ `origin_rule` value)
Options (label → stored value):
- `Any HQ` → `""`
- `Only foreign HQ` → `"foreign_hq"`
- `Only domestic HQ` → `"domestic_hq"` *(newly made functional — see Backend)*

The API returns `origin` as the raw `origin_rule` value; the UI maps value ↔
label. Unknown/legacy values map to `Any HQ` (lenient).

### Focus — text (soft signal)
`focus text`.

### Seeds — `TagEditor` (editable)
Add/remove discovery-query hints → `seeds text[]`. Inline "type + Enter" add
(reuse `TagEditor`). Auto-generation deferred.

---

## Persistence

- **Client** (`lib/api/lenses.ts`): add `createLens(patch)` → `POST /api/lenses`,
  `updateLens(id, patch)` → `PATCH /api/lenses/{id}`, `deleteLens(id)` →
  `DELETE /api/lenses/{id}`. Keep `getLenses()`.
- **BFF route** (`app/api/lenses/route.ts` + a new `app/api/lenses/[id]/route.ts`):
  add `POST` (list route) and `PATCH` / `DELETE` (id route), proxying via
  `bffFetch` (mirroring the jobs/companies id-route pattern).
- The create/update body carries `{ name, short, scope, modes, origin, focus,
  seeds, active }` (camelCase); `origin` sends the `origin_rule` value.

---

## Backend changes (two, small and justified)

1. **`derive_loc` — add a `domestic_hq` branch** (`services/jobs.py`) so the "Only
   domestic HQ" option actually scores instead of being stored-but-inert:
   ```python
   if origin_rule == "foreign_hq":
       factor += 8 if (hq and country and hq != country) else -8
   elif origin_rule == "domestic_hq":
       factor += 8 if (hq and country and hq == country) else -8
   ```
   + a scoring unit test for the domestic branch.
2. **Expose `isDefault` in `LensSummaryOut`** (`schemas/lens.py` + the router's
   `_summary`) so the frontend can filter/protect the default lens. Read-only
   passthrough of `lens.is_default`; no new column.

No other backend change — CRUD, `scope`/`modes`/`seeds` handling, and the schema
otherwise stay as-is.

---

## Components

- **`ProfilesView`** (rewrite): owns the lens list, which card is editing, create,
  and persistence. Filters the default lens from the editable list; renders each
  non-default lens as a read-only `LensCard` or an inline `LensEditor`.
- **`LensCard`** (read-only): name, derived count/new, scope/modes/origin/focus/
  seeds display, Edit affordance, active toggle.
- **`LensEditor`** (inline edit form): name input, structured scope (type picker +
  region/country dropdowns / city text), `ChipMultiSelect` modes, origin select,
  focus text, seeds `TagEditor`, dirty-state Save / Cancel / Delete.
- Reuse: `ChipMultiSelect`, `TagEditor`, `Toggle`, `Button`, `Field`.

## Constants / catalogs (frontend-only)

`apps/web/src/lib/lens-catalog.ts`:
- `SCOPE_TYPES = ["Any","Region","Country","City"]`
- `REGIONS: string[]` — curated (e.g. `EU, EEA, Eurozone, Nordics, DACH, Benelux,
  UK & Ireland, Southern Europe, North America, LATAM, Global`).
- `COUNTRIES: [code, name][]` — curated (EU/EEA + major: NL, DE, FR, ES, IT, PT,
  BE, IE, DK, SE, NO, FI, PL, AT, CH, CZ, GB, US, CA — extendable).
- `ORIGIN_OPTIONS: { label, value }[]` — the three origin mappings above.
- `parseScope(text)` / `serializeScope({type,value})` helpers (unit-tested).

These are UI catalogs; the backend does not validate them (scope/origin stay free
`text`), so an out-of-catalog stored value still reads/renders leniently.

## Validation

Frontend-only (the pickers constrain input); backend stays permissive
`text`/`text[]`. Reads are lenient (unknown origin → `Any HQ`; scope parsed
best-effort) — no strict server enum, so `GET /lenses` never 500s on legacy data.

---

## Testing (TDD)

- **`lens-catalog` / scope helpers:** `parseScope`/`serializeScope` round-trip
  (Any/Region/Country/City); origin value↔label mapping incl. unknown → Any HQ.
- **`LensEditor` component:** edit each field; modes toggle; scope type switch
  swaps the value control (Region/Country dropdown ↔ City text); seed add/remove;
  dirty-state gates Save; Save/Cancel/Delete callbacks fire with the right data.
- **`ProfilesView`:** "+ New profile" adds an editable card; the default lens is
  not in the editable list; toggle persists (`PATCH`); create/edit/delete call the
  right client functions with the mapped payload (scope serialized, origin value).
- **API:** `derive_loc` domestic-HQ scoring test (bonus when `hq == country`,
  penalty otherwise); `LensSummaryOut` includes `isDefault`. (CRUD endpoints
  already have `test_lenses_api.py`.)

## Files touched (indicative)

- `apps/api/specula_api/services/jobs.py` (`derive_loc` domestic branch)
- `apps/api/specula_api/schemas/lens.py` + `routers/lenses.py` (`isDefault` in summary)
- `apps/api/tests/` (derive_loc + summary tests)
- `packages/shared-types/src/index.ts` (`Lens`/`LensSummary` gain `isDefault: boolean`)
- `apps/web/src/lib/api/lenses.ts` (`createLens`/`updateLens`/`deleteLens`)
- `apps/web/src/app/api/lenses/route.ts` (add `POST`) + `app/api/lenses/[id]/route.ts` (new: `PATCH`/`DELETE`)
- `apps/web/src/lib/lens-catalog.ts` (new: catalogs + scope/origin helpers)
- `apps/web/src/components/profiles/profiles-view.tsx` (rewrite) + `lens-card.tsx` / `lens-editor.tsx` (new) + tests
- `apps/web/src/lib/seed/data.ts` (normalize lens `origin` to `origin_rule` values; add `isDefault`)
