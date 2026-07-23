# Candidate Profile completion — design

**Date:** 2026-07-22 (rev. 2026-07-23) · **Milestone:** M6 (Polish & launch) · **Status:** approved for planning

## Problem

The `/candidate` ("Candidate profile") page is half-finished. Some fields are
free-text where they should be constrained choices, and four sections cannot be
edited at all — they only render seed data:

| Field | Current UI | Issue |
|---|---|---|
| Headline, Location | free-text input | fine |
| Years experience | number input | fine |
| Work mode | free-text input | should be constrained choices |
| Visa | free-text input | should be constrained choices |
| Skills | tag editor | fine |
| Projects | renders seed only | **not editable** |
| Experience | renders seed only | **not editable** |
| Education | renders seed only (single line) | **not editable** |
| Languages | renders seed only | **not editable** |

The current save flow silently re-sends the stored seed values for the four
non-editable sections (`education`, `languages`, `projects`, `experience` are
passed straight from `c.*` in `handleSave`).

## Goal

Turn `/candidate` into a fully-editable, structured profile that collects
high-quality, low-freeform data:

1. Convert free-text fields to constrained inputs (work mode, visa) and
   **structured year pickers** for experience/education dates.
2. Make the four read-only sections editable with structured row editors.
3. Add **skill suggestions** (typeahead over a bundled common-skills list) to
   reduce free-text drift on the one field that actually drives matching.
4. Fold in two chosen polish improvements: **actionable skills-gap** and
   **better save UX (dirty-state)**.

The backend already persists every field (`candidate_profiles` has columns/JSONB
for all of them), so this is **frontend completion + structural migrations +
validation**. No new endpoints.

## Non-goals (explicitly out of scope)

- CV / LinkedIn import or parsing — deliberate product non-goal (spec §55; the
  profile stays an explicit hand-built form).
- Profile completeness meter and "how fields feed scoring" annotations —
  considered and dropped (YAGNI).
- Wiring skill re-embedding on write. `upsert_candidate` does **not** currently
  re-embed skills although spec §504 says it should. This is a pre-existing
  spec/code gap; it is noted but **not** fixed here.
- **Location autocomplete** — evaluated (bundled city list / Photon-OSM / Google
  Places). Deferred: candidate location is a non-scoring personal descriptor
  (spec §4.2), so typeahead here is polish, not data quality. Location stays a
  plain text input.
- **Achievements / impact highlights** — deferred to a fast follow-up. Bounded
  per-role highlights would help match rationale and CV-bullet drafting, but it's
  a scope expansion beyond finishing the page (and nudges toward a parsed-CV feel).

## Product constraints carried in from the spec

- `work_mode` / `location` on the candidate profile are **personal descriptors
  only** — never a filter or scoring input (spec §4.2). They pre-fill the first
  lens at onboarding. So structuring work mode here is data hygiene, not
  behavioral change.
- Candidate `visa` is likewise a personal descriptor; visa *fit* in scoring uses
  the **posting's** visa field against the active lens, not this field.

---

## Field specification

### Work mode — multi-select `Mode[]`
- Input: three chip-toggles for `Remote` / `Hybrid` / `On-site` (the existing
  `Mode` union in `shared-types`). Any subset may be selected.
- Type change: `Candidate.workMode: string` → `Mode[]`.
- Seed value `"Remote-first (EU)"` becomes `["Remote", "Hybrid", "On-site"]`.

### Visa — single-select, 4 EU options
Stored as the option's stable string value. Options:
1. `EU/EEA/Swiss citizen — no sponsorship`
2. `Have EU work/residence permit — no sponsorship`
3. `Require visa sponsorship`
4. `Require relocation + sponsorship`

Rendered as a styled native `<select>` (codebase convention — no `Select` atom
exists). Seed maps `"EU citizen — no sponsorship needed"` → option 1.

### Languages — structured `{language, level}[]`
- Row editor: each row is a free-text `language` plus a `level` picked from a
  CEFR-style list: `Native · C2 · C1 · B2 · B1 · A2 · A1`.
- Type change: `Candidate.languages: string[]` → `{ language: string; level: CefrLevel }[]`.
- Seed `["English (native-level)", "Dutch (native)", "German (B1)"]` becomes
  `[{language:"English", level:"Native"}, {language:"Dutch", level:"Native"},
  {language:"German", level:"B1"}]`.

### Education — structured `{degree, field, institution, year}[]`
- Row editor. `year` is a **completion year picked from a year `<select>`**
  (constrained, not free text), typed `number | null`.
- Type change: `Candidate.education: string` →
  `{ degree: string; field: string; institution: string; year: number | null }[]`.
- Seed `"MSc Artificial Intelligence — University of Amsterdam"` becomes
  `[{degree:"MSc", field:"Artificial Intelligence",
  institution:"University of Amsterdam", year:2019}]`.

### Projects — `{name, note}[]` (shape unchanged, now editable)
- Row editor: add / edit / remove rows of `{name, note}`.

### Experience — structured `{role, org, startYear, endYear}[]`
- Row editor: add / edit / remove rows. `startYear` / `endYear` are **year
  `<select>`s** (constrained, replacing the old free-text `period`). `endYear =
  null` renders as **"Present"** (ongoing role); tenure is then computable.
- Shape change: `{role, org, period}` → `{role, org, startYear: number | null,
  endYear: number | null }`.
- Seed becomes `[{role:"Senior Data Scientist", org:"Mollie", startYear:2022,
  endYear:null}, {role:"ML Engineer", org:"Adyen", startYear:2019, endYear:2022}]`.

### Skills — tag editor + suggestions
- Keeps the `TagEditor` chip model, plus a **typeahead** over a bundled
  common-skills list (native `<datalist>`), with **free-add fallback** (any typed
  value is still accepted). Frontend-only; **no schema change** (`skills` stays
  `text[]`).
- Rationale: skills are canonicalized and drive the skill factor, so reducing
  free-text drift here improves match quality — unlike location, which is
  non-scoring. The common-skills list is a small curated static asset in the web app.

### Unchanged
Headline (free text), **Location (free text — autocomplete deferred, see
non-goals)**, Years experience (number ≥ 0).

---

## Actionable skills-gap

The right-hand Skills-Gap panel is computed server-side (`compute_skills_gap`):
required skills across the user's trusted target-role postings that are **not**
already on the profile.

- **Display filter:** show `skillsGap` filtered to exclude skills already on the
  current (in-memory) profile, case-insensitively — this mirrors the server's own
  `sk.casefold() not in have` logic, so the panel stays reactive with no new
  endpoint.
- **One-click add:** each gap row gets a `+ add` action that appends the skill to
  the Skills chips. The row then disappears (via the display filter). Removing the
  chip makes it reappear. On reload the server recomputes identically.

No API or schema change — purely a client interaction over existing data.

---

## Save UX — dirty-state, no autosave

- Compute a `dirty` flag by comparing the current form state against the
  last-saved snapshot.
- "Save profile" button is **disabled when clean**.
- Show an "Unsaved changes" hint when dirty; keep the existing "Saved."
  confirmation after a successful save; snapshot becomes the new baseline.
- **No autosave** — explicit save is simpler and cost-safe (guards against future
  re-embedding cost on write).

---

## Data model changes — one Alembic migration

Only demo-seeded data exists, so column-type changes are low-risk. A single
migration alters three columns on `candidate_profiles`:

| Column | From | To | Data migration |
|---|---|---|---|
| `work_mode` | `text` | `text[]` | wrap existing scalar into a one-element array |
| `languages` | `text[]` | `jsonb` | each string → `{language: <str>, level: ""}` (best-effort) |
| `education` | `text` | `jsonb` | existing string → `[{degree:"", field:<str>, institution:"", year:null}]` |

The migration must be reversible (`downgrade` collapses arrays/JSONB back to the
scalar/`text[]` forms, best-effort).

`projects` and `experience` stay `jsonb` — **no column-type change**. But
`experience` **objects change shape** (`period` → `startYear`/`endYear`), so the
same migration best-effort rewrites existing rows: parse a `period` like
`"2022 — now"` → `{startYear:2022, endYear:null}`; unparseable periods drop to
`{startYear:null, endYear:null}` (demo data only, low risk). `projects`
(`{name, note}`) is untouched.

---

## Validation — frontend + backend

Enum constraints enforced in both layers (defense-in-depth; "structured, not
trusted" ethos):

- **Frontend:** dropdowns / chip-toggles / year `<select>`s constrain input by
  construction; the skills typeahead suggests but still allows free-add.
- **Backend:** Pydantic `CandidateIn` uses `Literal`/`Enum` for `visa`, work
  mode members, and language `level`; rejects out-of-set values. Year fields
  (`startYear`, `endYear`, education `year`) are `int | None` with a sane range
  bound (e.g. 1950–2100). `skills` remain free `list[str]` (suggestions are a UI
  affordance, not a server constraint).

Enum source of truth: defined in `packages/shared-types` (TS) and **mirrored** in
a Python constants module (`schemas/candidate` or a small `constants` module).
The two lists are kept in sync manually (small, stable lists); a note in both
files points at the other.

---

## Components

New small, isolated, individually testable editors, each following the existing
`TagEditor` add/remove-row pattern and wrapped in the existing `Field` label:

- `ModeSelect` — multi-select chip toggles for `Mode[]`.
- Visa `<select>` — styled native select (inline or a tiny wrapper).
- `YearSelect` — shared year `<select>` primitive (blank + year range; optional
  "Present" sentinel that maps to `null` for experience end).
- `LanguageEditor` — rows of `{language, level}` with a CEFR `<select>`.
- `EducationEditor` — rows of `{degree, field, institution, year}` (year via `YearSelect`).
- `ProjectEditor` — rows of `{name, note}`.
- `ExperienceEditor` — rows of `{role, org, startYear, endYear}` (years via `YearSelect`).
- Skills input — extend `TagEditor` (or a thin `SkillEditor` wrapper) with a
  `<datalist>` typeahead over the bundled common-skills list; free-add preserved.

`candidate-view.tsx` wires them together, owns form state, the dirty flag, and
the skills-gap add-flow.

---

## Testing (TDD)

- **Component tests** per editor: add, edit, remove a row; year `<select>`
  behavior (incl. `endYear=null` → "Present"); skills typeahead still allows a
  free-add value.
- **`candidate-view` tests:** dirty-state gates the Save button; skills-gap
  `+ add` moves a skill into Skills and removes the gap row.
- **API tests:** Pydantic rejects an out-of-set visa / mode / level; accepts
  valid structured payloads.
- **Migration test:** upgrade→downgrade round-trip on a seeded row preserves
  representable data.

## Files touched (indicative)

- `apps/web/src/components/candidate/candidate-view.tsx` (+ test)
- `apps/web/src/components/candidate/*` (new editor components + tests)
- `apps/web/src/components/atoms/` (if a shared select/row primitive is extracted)
- `apps/web/src/lib/api/candidate.ts` (BFF mapping for new shapes)
- `apps/web/src/lib/seed/data.ts` (restructured seed)
- `apps/web/src/lib/skills-catalog.ts` (bundled common-skills suggestion list — new)
- `packages/shared-types/src/index.ts` (`Candidate`, new `CefrLevel`, visa/enum types)
- `apps/api/specula_api/schemas/candidate.py` (structured fields + `Literal`/`Enum`)
- `apps/api/.../db/models/candidate_profile.py` (column types)
- `apps/api/.../services/candidate.py` (upsert unaffected; verify JSONB round-trip)
- new Alembic migration (+ test)
- Python demo seeder (restructured candidate seed)
