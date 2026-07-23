# Candidate Profile Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/candidate` into a fully-editable, structured profile — constrained inputs (work mode, visa, CEFR levels, year pickers), editable projects/experience/education/languages, skill suggestions, an actionable skills-gap, and a dirty-state save.

**Architecture:** Backend `candidate_profiles` gains structured shapes via one Alembic migration + Pydantic `Literal`/nested-model validation (no new endpoints; `PUT /candidate` stays a full replace). Frontend adds small, isolated editor components consumed by a rewritten `candidate-view.tsx`. Enum option arrays live once in `@specula/shared-types` (consumed as source) and are mirrored as Python `Literal`s.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · pytest (`apps/api`); Next 16 · React 19 · TypeScript strict · Tailwind · Vitest + Testing Library (`apps/web`); shared TS types in `packages/shared-types`.

## Global Constraints

- **No new endpoints.** `GET`/`PUT /candidate` only; `PUT` is a full replace. `upsert_candidate` is unchanged (it does not re-embed skills — pre-existing gap, out of scope).
- **Skills stay free** `list[str]` server-side. The common-skills catalog is a **frontend suggestion affordance only** (free-add always accepted). No skills enum on the backend.
- **Location stays free text.** No autocomplete (candidate location is a non-scoring descriptor). Achievements/highlights are out of scope (deferred follow-up).
- **Enum source of truth:** `packages/shared-types/src/index.ts` (TS), **mirrored verbatim** in `apps/api/specula_api/schemas/candidate.py` (Python `Literal`). Both files carry a sync note pointing at the other.
- **Exact enum string values** (use verbatim, em-dash `—` U+2014):
  - Work modes: `Remote`, `Hybrid`, `On-site`
  - Visa: `EU/EEA/Swiss citizen — no sponsorship`, `Have EU work/residence permit — no sponsorship`, `Require visa sponsorship`, `Require relocation + sponsorship`
  - CEFR levels: `Native`, `C2`, `C1`, `B2`, `B1`, `A2`, `A1`
- **Year fields** (`experience.startYear`/`endYear`, `education.year`) are `int | null`, valid range **1950–2100**; `null` end-year renders as **"Present"**.
- **DB tests need docker Postgres.** Start it with `just up` before running `pytest`; `@requires_db` tests skip when no DB. Migrations apply via the `migrated_db` fixture.
- **Run commands:** `just typecheck` (mypy + tsc), `just test` (pytest + vitest), `just migrate`, `just seed`, `just up`. Single web test: `cd apps/web && pnpm vitest run <path>`. Single api test: `cd apps/api && uv run pytest tests/<file>::<test> -v`.
- **Next 16 is not the Next you know** — per `apps/web/AGENTS.md`, check `node_modules/next/dist/docs/` before using unfamiliar Next APIs. This plan uses only client components and no new Next APIs.

---

### Task 1: Shared TS types, enum arrays, skills catalog (frontend foundation)

Additive only — does **not** change the `Candidate` interface yet (that flip is Task 11), so `pnpm typecheck` stays green.

**Files:**
- Modify: `packages/shared-types/src/index.ts`
- Create: `apps/web/src/lib/skills-catalog.ts`

**Interfaces:**
- Produces: `CefrLevel`, `Visa`, `LanguageEntry`, `EducationEntry`, `ProjectEntry`, `ExperienceEntry` (types); `CEFR_LEVELS`, `VISA_OPTIONS`, `WORK_MODES` (runtime arrays); `COMMON_SKILLS: string[]`.

- [ ] **Step 1: Add types + enum arrays to shared-types**

Insert immediately **above** the existing `export interface Candidate {` line in `packages/shared-types/src/index.ts`:

```ts
// ⚠ Enum source of truth. Mirrored in apps/api/specula_api/schemas/candidate.py
// (Mode / Visa / CefrLevel Literals). Keep both in sync.
export type CefrLevel = "Native" | "C2" | "C1" | "B2" | "B1" | "A2" | "A1";
export const CEFR_LEVELS: readonly CefrLevel[] = [
  "Native", "C2", "C1", "B2", "B1", "A2", "A1",
];

export const VISA_OPTIONS = [
  "EU/EEA/Swiss citizen — no sponsorship",
  "Have EU work/residence permit — no sponsorship",
  "Require visa sponsorship",
  "Require relocation + sponsorship",
] as const;
export type Visa = (typeof VISA_OPTIONS)[number];

export const WORK_MODES: readonly Mode[] = ["Remote", "Hybrid", "On-site"];

export interface LanguageEntry { language: string; level: CefrLevel }
export interface EducationEntry {
  degree: string; field: string; institution: string; year: number | null;
}
export interface ProjectEntry { name: string; note: string }
export interface ExperienceEntry {
  role: string; org: string; startYear: number | null; endYear: number | null;
}
```

- [ ] **Step 2: Create the skills catalog**

Create `apps/web/src/lib/skills-catalog.ts`:

```ts
// Frontend-only suggestion list for the Skills typeahead (a <datalist>). NOT a
// server constraint — any typed value is still accepted (free-add). Nudges toward
// canonical spellings so matching (which canonicalizes skills) stays clean.
export const COMMON_SKILLS: string[] = [
  "Python", "PyTorch", "TensorFlow", "JAX", "Hugging Face", "LLM fine-tuning",
  "RAG", "LangGraph", "LangChain", "vLLM", "Triton / TensorRT", "ONNX",
  "Distributed training", "Ray", "Spark", "Airflow", "dbt", "Snowflake", "Kafka",
  "Pandas", "NumPy", "scikit-learn", "XGBoost", "MLflow", "Weights & Biases",
  "Kubeflow", "Prompt engineering", "pgvector", "AWS", "GCP", "Azure", "Docker",
  "Kubernetes", "Terraform", "SQL", "FastAPI", "Go", "Rust", "TypeScript",
  "React", "Redis", "PostgreSQL",
];
```

- [ ] **Step 3: Verify typecheck passes**

Run: `cd apps/web && pnpm typecheck`
Expected: exits 0 (no errors — additions only).

- [ ] **Step 4: Commit**

```bash
git add packages/shared-types/src/index.ts apps/web/src/lib/skills-catalog.ts
git commit -m "feat(candidate): add structured TS types, enum arrays, skills catalog"
```

---

### Task 2: Backend structured schema, model, migration, tests

**Files:**
- Modify: `apps/api/specula_api/schemas/candidate.py`
- Modify: `apps/api/specula_api/db/models/candidate_profile.py`
- Create: `apps/api/alembic/versions/c8f1a2b3d4e5_candidate_structured_fields.py`
- Modify: `apps/api/tests/test_candidate_api.py`
- Create: `apps/api/tests/test_candidate_migration.py`

**Interfaces:**
- Produces (API contract, camelCase over JSON): `workMode: Mode[]`, `visa: Visa | null`, `languages: {language, level}[]`, `education: {degree, field, institution, year}[]`, `experience: {role, org, startYear, endYear}[]`, `projects: {name, note}[]`, `skills: string[]`.
- Consumes: current Alembic head `5f2f2fb3a1af`.

- [ ] **Step 1: Start local DB (once)**

Run: `just up`
Expected: docker Postgres container up on the dev port.

- [ ] **Step 2: Write the failing API tests (new shapes + rejection)**

Replace the body of the three existing tests in `apps/api/tests/test_candidate_api.py` and add a rejection test. Keep the imports and the `_service_jwt_secret` fixture / `_auth_header` helper at the top unchanged. Replace everything from the first `@requires_db` to the end of the file with:

```python
@requires_db
async def test_get_candidate_for_fresh_user_returns_empty_defaults(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/candidate", headers=_auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["headline"] is None
    assert body["location"] is None
    assert body["workMode"] == []
    assert body["visa"] is None
    assert body["years"] is None
    assert body["education"] == []
    assert body["languages"] == []
    assert body["skills"] == []
    assert body["projects"] == []
    assert body["experience"] == []


_VALID_PAYLOAD = {
    "headline": "ML Engineer",
    "location": "Berlin",
    "workMode": ["Remote", "Hybrid"],
    "visa": "Require visa sponsorship",
    "years": 7,
    "education": [
        {"degree": "MSc", "field": "CS", "institution": "TU Berlin", "year": 2018},
    ],
    "languages": [{"language": "English", "level": "C2"}],
    "skills": ["Python", "PyTorch"],
    "projects": [{"name": "Specula", "note": "role ledger"}],
    "experience": [
        {"role": "ML Eng", "org": "Acme", "startYear": 2021, "endYear": None},
    ],
}


@requires_db
async def test_put_candidate_persists_structured_shapes(migrated_db: None) -> None:
    headers = _auth_header()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/candidate", json=_VALID_PAYLOAD, headers=headers)
        assert put_response.status_code == 200
        put_body = put_response.json()
        for key, value in _VALID_PAYLOAD.items():
            assert put_body[key] == value

        get_body = (await client.get("/api/v1/candidate", headers=headers)).json()
        for key, value in _VALID_PAYLOAD.items():
            assert get_body[key] == value


@requires_db
async def test_put_candidate_rejects_out_of_set_values(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    bad_bodies = [
        {**_VALID_PAYLOAD, "visa": "not a real option"},
        {**_VALID_PAYLOAD, "workMode": ["Telepathy"]},
        {**_VALID_PAYLOAD, "languages": [{"language": "English", "level": "Z9"}]},
        {**_VALID_PAYLOAD, "experience": [
            {"role": "r", "org": "o", "startYear": 1000, "endYear": 2020}]},
    ]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for body in bad_bodies:
            resp = await client.put("/api/v1/candidate", json=body, headers=_auth_header())
            assert resp.status_code == 422, body


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    user_a_headers = _auth_header()
    user_b_headers = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put(
            "/api/v1/candidate", json=_VALID_PAYLOAD, headers=user_a_headers
        )
        assert put_response.status_code == 200

        body = (await client.get("/api/v1/candidate", headers=user_b_headers)).json()
        assert body["headline"] is None
        assert body["skills"] == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_candidate_api.py -v`
Expected: FAIL — fresh user still returns `workMode: None` (not `[]`); rejection test fails because free-text is currently accepted (200 not 422).

- [ ] **Step 4: Rewrite the Pydantic schema with nested models + Literals**

Replace the entire contents of `apps/api/specula_api/schemas/candidate.py` with:

```python
from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field
from pydantic import BaseModel
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ⚠ Enum source of truth is packages/shared-types/src/index.ts
# (WORK_MODES / VISA_OPTIONS / CEFR_LEVELS). Keep these Literals in sync.
Mode = Literal["Remote", "Hybrid", "On-site"]
Visa = Literal[
    "EU/EEA/Swiss citizen — no sponsorship",
    "Have EU work/residence permit — no sponsorship",
    "Require visa sponsorship",
    "Require relocation + sponsorship",
]
CefrLevel = Literal["Native", "C2", "C1", "B2", "B1", "A2", "A1"]
Year = Annotated[int, Field(ge=1950, le=2100)]


class LanguageEntry(CamelModel):
    language: str
    level: CefrLevel


class EducationEntry(CamelModel):
    degree: str = ""
    field: str = ""
    institution: str = ""
    year: Year | None = None


class ProjectEntry(CamelModel):
    name: str = ""
    note: str = ""


class ExperienceEntry(CamelModel):
    role: str = ""
    org: str = ""
    start_year: Year | None = None
    end_year: Year | None = None


class CandidateIn(CamelModel):
    headline: str | None = None
    location: str | None = None
    work_mode: list[Mode] = []
    visa: Visa | None = None
    years: int | None = None
    education: list[EducationEntry] = []
    languages: list[LanguageEntry] = []
    skills: list[str] = []
    projects: list[ProjectEntry] = []
    experience: list[ExperienceEntry] = []


class CandidateOut(CandidateIn):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
```

- [ ] **Step 5: Update the ORM column types**

In `apps/api/specula_api/db/models/candidate_profile.py`, replace the five field lines (`work_mode` through `experience`; leave `user_id`, `headline`, `location`, `visa`, `years`, `skills_vec` as-is) with:

```python
    work_mode: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    visa: Mapped[str | None] = mapped_column(Text, nullable=True)
    years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[list[object]] = mapped_column(JSONB, server_default=text("'[]'"))
    languages: Mapped[list[object]] = mapped_column(JSONB, server_default=text("'[]'"))
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    projects: Mapped[list[object]] = mapped_column(JSONB, server_default=text("'[]'"))
    experience: Mapped[list[object]] = mapped_column(JSONB, server_default=text("'[]'"))
```

(The existing imports `from sqlalchemy import ARRAY, Integer, Text, text` and `from sqlalchemy.dialects.postgresql import JSONB` already cover this.)

- [ ] **Step 6: Create the Alembic migration**

Create `apps/api/alembic/versions/c8f1a2b3d4e5_candidate_structured_fields.py`:

```python
"""candidate profile structured fields

work_mode text -> text[]; languages text[] -> jsonb; education text -> jsonb.
experience stays jsonb but its objects change shape (period -> startYear/endYear).
Only demo-seeded data exists; conversions are best-effort and reversible.

Revision ID: c8f1a2b3d4e5
Revises: 5f2f2fb3a1af
"""

from alembic import op

revision = "c8f1a2b3d4e5"
down_revision = "5f2f2fb3a1af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # work_mode: text -> text[] (wrap a non-empty scalar into a one-element array)
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN work_mode TYPE text[] "
        "USING (CASE WHEN work_mode IS NULL OR work_mode = '' "
        "THEN '{}'::text[] ELSE ARRAY[work_mode] END)"
    )
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode SET DEFAULT '{}'")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode SET NOT NULL")

    # languages: text[] -> jsonb [{language, level:""}]
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages DROP DEFAULT")
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN languages TYPE jsonb USING coalesce("
        "(SELECT jsonb_agg(jsonb_build_object('language', e, 'level', '')) "
        "FROM unnest(languages) AS e), '[]'::jsonb)"
    )
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages SET DEFAULT '[]'::jsonb")

    # education: text -> jsonb [{degree, field, institution, year}]
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN education TYPE jsonb "
        "USING (CASE WHEN education IS NULL OR education = '' THEN '[]'::jsonb "
        "ELSE jsonb_build_array(jsonb_build_object("
        "'degree','', 'field', education, 'institution','', 'year', NULL)) END)"
    )
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education SET DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education SET NOT NULL")

    # experience: rewrite {role, org, period} -> {role, org, start_year, end_year}
    op.execute(
        r"""
        UPDATE candidate_profiles SET experience = coalesce((
            SELECT jsonb_agg(jsonb_build_object(
                'role', e->>'role',
                'org', e->>'org',
                'start_year', NULLIF(substring(e->>'period' from '(\d{4})'), '')::int,
                'end_year', CASE
                    WHEN e->>'period' ~* 'now|present' THEN NULL
                    ELSE NULLIF(substring(e->>'period' from '(\d{4})\D*$'), '')::int
                END))
            FROM jsonb_array_elements(experience) AS e)
        , '[]'::jsonb)
        WHERE jsonb_typeof(experience) = 'array'
          AND experience @> '[{"period": null}]' IS NOT TRUE
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements(experience) AS e WHERE e ? 'period')
        """
    )


def downgrade() -> None:
    # experience: {start_year, end_year} -> {period}
    op.execute(
        """
        UPDATE candidate_profiles SET experience = coalesce((
            SELECT jsonb_agg(jsonb_build_object(
                'role', e->>'role',
                'org', e->>'org',
                'period', concat_ws(' — ', e->>'start_year',
                    coalesce(e->>'end_year', 'now'))))
            FROM jsonb_array_elements(experience) AS e)
        , '[]'::jsonb)
        WHERE jsonb_typeof(experience) = 'array'
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements(experience) AS e WHERE e ? 'start_year')
        """
    )

    # education: jsonb -> text (first row's field)
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education DROP DEFAULT")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education DROP NOT NULL")
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN education TYPE text "
        "USING (CASE WHEN jsonb_array_length(education) = 0 THEN NULL "
        "ELSE education->0->>'field' END)"
    )

    # languages: jsonb -> text[]
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages DROP DEFAULT")
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN languages TYPE text[] USING coalesce("
        "(SELECT array_agg(e->>'language') FROM jsonb_array_elements(languages) AS e), "
        "'{}'::text[])"
    )
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages SET DEFAULT '{}'")

    # work_mode: text[] -> text (join)
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode DROP DEFAULT")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode DROP NOT NULL")
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN work_mode TYPE text "
        "USING (CASE WHEN cardinality(work_mode) = 0 THEN NULL "
        "ELSE array_to_string(work_mode, ', ') END)"
    )
```

- [ ] **Step 7: Run the API tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_candidate_api.py -v`
Expected: PASS (the `migrated_db` fixture applies the new migration to a fresh test DB).

- [ ] **Step 8: Write the migration column-type test**

Create `apps/api/tests/test_candidate_migration.py`:

```python
from sqlalchemy import text
from test_db import requires_db

from specula_api.db.session import async_session


@requires_db
async def test_candidate_profiles_column_types(migrated_db: None) -> None:
    async with async_session() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = 'candidate_profiles'"
                )
            )
        ).all()
    types = {name: dtype for name, dtype in rows}
    assert types["work_mode"] == "ARRAY"
    assert types["languages"] == "jsonb"
    assert types["education"] == "jsonb"
    assert types["experience"] == "jsonb"
```

- [ ] **Step 9: Run the migration test + mypy**

Run: `cd apps/api && uv run pytest tests/test_candidate_migration.py -v && uv run mypy .`
Expected: test PASS; mypy reports no errors.

- [ ] **Step 10: Commit**

```bash
git add apps/api/specula_api/schemas/candidate.py \
  apps/api/specula_api/db/models/candidate_profile.py \
  apps/api/alembic/versions/c8f1a2b3d4e5_candidate_structured_fields.py \
  apps/api/tests/test_candidate_api.py apps/api/tests/test_candidate_migration.py
git commit -m "feat(candidate): structured backend schema + migration + validation"
```

---

### Task 3: Restructure the Python demo seeder

**Files:**
- Modify: `apps/api/specula_api/seed.py` (the `CandidateProfile(...)` insert, ~line 930)

**Interfaces:**
- Consumes: the migrated schema (Task 2). Stores JSONB with **snake_case** keys (`start_year`/`end_year`) — matching what `upsert_candidate` writes via `model_dump()`.

- [ ] **Step 1: Update the candidate seed values**

In `apps/api/specula_api/seed.py`, within the `CandidateProfile(` insert, replace the `work_mode`, `visa`, `education`, and `languages` argument lines, and (further down in the same constructor) the `experience` argument, so the constructor reads:

```python
        CandidateProfile(
            user_id=uid,
            headline="Data Scientist / ML Engineer",
            location="Amsterdam, NL",
            work_mode=["Remote", "Hybrid", "On-site"],
            visa="EU/EEA/Swiss citizen — no sponsorship",
            years=6,
            education=[
                {
                    "degree": "MSc",
                    "field": "Artificial Intelligence",
                    "institution": "University of Amsterdam",
                    "year": 2019,
                }
            ],
            languages=[
                {"language": "English", "level": "Native"},
                {"language": "Dutch", "level": "Native"},
                {"language": "German", "level": "B1"},
            ],
            skills=[
```

Leave the `skills=[...]` list and `projects=[...]` list exactly as they are. Then update the `experience=[...]` argument (same constructor) to:

```python
            experience=[
                {"role": "Senior Data Scientist", "org": "Mollie",
                 "start_year": 2022, "end_year": None},
                {"role": "ML Engineer", "org": "Adyen",
                 "start_year": 2019, "end_year": 2022},
            ],
```

- [ ] **Step 2: Migrate + reseed to verify it runs clean**

Run: `just migrate && just seed`
Expected: both commands exit 0; seeder prints its normal completion output with no validation/JSON errors.

- [ ] **Step 3: Verify the seeded row reads back through the API shapes**

Run: `cd apps/api && uv run pytest tests/test_candidate_api.py -v`
Expected: still PASS (sanity — seeder change must not break the schema).

- [ ] **Step 4: Commit**

```bash
git add apps/api/specula_api/seed.py
git commit -m "feat(candidate): restructure demo seeder to structured candidate fields"
```

---

### Task 4: `ModeSelect` component

**Files:**
- Create: `apps/web/src/components/candidate/mode-select.tsx`
- Test: `apps/web/src/components/candidate/mode-select.test.tsx`

**Interfaces:**
- Consumes: `WORK_MODES`, `Mode` (Task 1).
- Produces: `<ModeSelect value={Mode[]} onChange={(v: Mode[]) => void} />`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/candidate/mode-select.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ModeSelect } from "@/components/candidate/mode-select";

afterEach(cleanup);

describe("ModeSelect", () => {
  it("reflects selected modes via aria-pressed", () => {
    render(<ModeSelect value={["Remote"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Remote" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Hybrid" })).toHaveAttribute("aria-pressed", "false");
  });

  it("adds a mode when an off toggle is clicked", () => {
    const onChange = vi.fn();
    render(<ModeSelect value={["Remote"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Hybrid" }));
    expect(onChange).toHaveBeenCalledWith(["Remote", "Hybrid"]);
  });

  it("removes a mode when an on toggle is clicked", () => {
    const onChange = vi.fn();
    render(<ModeSelect value={["Remote", "Hybrid"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Remote" }));
    expect(onChange).toHaveBeenCalledWith(["Hybrid"]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/candidate/mode-select.test.tsx`
Expected: FAIL — cannot resolve `@/components/candidate/mode-select`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/candidate/mode-select.tsx`:

```tsx
"use client";

import type { Mode } from "@specula/shared-types";
import { WORK_MODES } from "@specula/shared-types";

export function ModeSelect({
  value,
  onChange,
}: {
  value: Mode[];
  onChange: (v: Mode[]) => void;
}) {
  const toggle = (m: Mode) =>
    onChange(value.includes(m) ? value.filter((x) => x !== m) : [...value, m]);

  return (
    <div className="flex flex-wrap gap-2">
      {WORK_MODES.map((m) => {
        const on = value.includes(m);
        return (
          <button
            key={m}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(m)}
            className={`rounded-[8px] border px-[15px] py-[10px] text-[12.5px] transition-colors ${
              on
                ? "border-ink bg-ink text-paper"
                : "border-rule-2 bg-panel text-ink hover:border-ink"
            }`}
          >
            {m}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/candidate/mode-select.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/candidate/mode-select.tsx apps/web/src/components/candidate/mode-select.test.tsx
git commit -m "feat(candidate): ModeSelect multi-select component"
```

---

### Task 5: `YearSelect` component

**Files:**
- Create: `apps/web/src/components/candidate/year-select.tsx`
- Test: `apps/web/src/components/candidate/year-select.test.tsx`

**Interfaces:**
- Produces: `<YearSelect value={number | null} onChange={(v: number | null) => void} ariaLabel={string} presentLabel?={string} />`. The blank/`null` option shows `presentLabel` when provided (e.g. `"Present"`), else `"—"`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/candidate/year-select.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { YearSelect } from "@/components/candidate/year-select";

afterEach(cleanup);

describe("YearSelect", () => {
  it("shows the current value as selected", () => {
    render(<YearSelect value={2019} onChange={() => {}} ariaLabel="Year" />);
    expect((screen.getByLabelText("Year") as HTMLSelectElement).value).toBe("2019");
  });

  it("emits a number when a year is chosen", () => {
    const onChange = vi.fn();
    render(<YearSelect value={null} onChange={onChange} ariaLabel="Year" />);
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: "2020" } });
    expect(onChange).toHaveBeenCalledWith(2020);
  });

  it("emits null when the blank option is chosen", () => {
    const onChange = vi.fn();
    render(<YearSelect value={2020} onChange={onChange} ariaLabel="End year" presentLabel="Present" />);
    expect(screen.getByRole("option", { name: "Present" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("End year"), { target: { value: "" } });
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/candidate/year-select.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/candidate/year-select.tsx`:

```tsx
"use client";

const MAX_YEAR = new Date().getFullYear() + 1;
const YEARS = Array.from({ length: MAX_YEAR - 1950 + 1 }, (_, i) => MAX_YEAR - i);

export function YearSelect({
  value,
  onChange,
  ariaLabel,
  presentLabel,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  ariaLabel: string;
  presentLabel?: string;
}) {
  return (
    <select
      aria-label={ariaLabel}
      value={value === null ? "" : String(value)}
      onChange={(e) =>
        onChange(e.target.value === "" ? null : Number(e.target.value))
      }
      className="w-full rounded-[6px] border border-rule bg-paper px-[8px] py-[8px] text-[12.5px] text-ink focus:border-ink focus:outline-none"
    >
      <option value="">{presentLabel ?? "—"}</option>
      {YEARS.map((y) => (
        <option key={y} value={String(y)}>
          {y}
        </option>
      ))}
    </select>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/candidate/year-select.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/candidate/year-select.tsx apps/web/src/components/candidate/year-select.test.tsx
git commit -m "feat(candidate): YearSelect component"
```

---

### Task 6: `LanguageEditor` component

**Files:**
- Create: `apps/web/src/components/candidate/language-editor.tsx`
- Test: `apps/web/src/components/candidate/language-editor.test.tsx`

**Interfaces:**
- Consumes: `LanguageEntry`, `CEFR_LEVELS` (Task 1).
- Produces: `<LanguageEditor value={LanguageEntry[]} onChange={(v) => void} />`. New rows default to `{ language: "", level: "Native" }`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/candidate/language-editor.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { LanguageEditor } from "@/components/candidate/language-editor";

afterEach(cleanup);
const rows = [{ language: "English", level: "Native" as const }];

describe("LanguageEditor", () => {
  it("adds a row with the default level", () => {
    const onChange = vi.fn();
    render(<LanguageEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add language"));
    expect(onChange).toHaveBeenCalledWith([
      { language: "English", level: "Native" },
      { language: "", level: "Native" },
    ]);
  });

  it("edits a row's language", () => {
    const onChange = vi.fn();
    render(<LanguageEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("language 1"), { target: { value: "Dutch" } });
    expect(onChange).toHaveBeenCalledWith([{ language: "Dutch", level: "Native" }]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<LanguageEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove language 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/candidate/language-editor.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/candidate/language-editor.tsx`:

```tsx
"use client";

import type { LanguageEntry } from "@specula/shared-types";
import { CEFR_LEVELS } from "@specula/shared-types";

const CIN =
  "w-full rounded-[6px] border border-rule bg-paper px-[10px] py-[8px] text-[12.5px] text-ink focus:border-ink focus:outline-none";

export function LanguageEditor({
  value,
  onChange,
}: {
  value: LanguageEntry[];
  onChange: (v: LanguageEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<LanguageEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () => onChange([...value, { language: "", level: "Native" }]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[1fr_128px_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={CIN}
              placeholder="Language"
              aria-label={`language ${i + 1}`}
              value={row.language}
              onChange={(e) => update(i, { language: e.target.value })}
            />
            <select
              className={CIN}
              aria-label={`level ${i + 1}`}
              value={row.level}
              onChange={(e) =>
                update(i, { level: e.target.value as LanguageEntry["level"] })
              }
            >
              {CEFR_LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
            <button
              type="button"
              aria-label={`remove language ${i + 1}`}
              onClick={() => remove(i)}
              className="justify-self-center font-mono text-[15px] text-ink-3 hover:text-warn"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={add}
        className="rounded-[7px] border border-dashed border-rule-2 bg-transparent px-3 py-[6px] text-[12.5px] text-ink-2 hover:border-ink hover:text-ink"
      >
        + add language
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/candidate/language-editor.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/candidate/language-editor.tsx apps/web/src/components/candidate/language-editor.test.tsx
git commit -m "feat(candidate): LanguageEditor component"
```

---

### Task 7: `EducationEditor` component

**Files:**
- Create: `apps/web/src/components/candidate/education-editor.tsx`
- Test: `apps/web/src/components/candidate/education-editor.test.tsx`

**Interfaces:**
- Consumes: `EducationEntry` (Task 1), `YearSelect` (Task 5).
- Produces: `<EducationEditor value={EducationEntry[]} onChange={(v) => void} />`. New rows default to `{ degree: "", field: "", institution: "", year: null }`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/candidate/education-editor.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { EducationEditor } from "@/components/candidate/education-editor";

afterEach(cleanup);
const rows = [{ degree: "MSc", field: "AI", institution: "UvA", year: 2019 }];

describe("EducationEditor", () => {
  it("adds a blank row", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add education"));
    expect(onChange).toHaveBeenCalledWith([
      rows[0],
      { degree: "", field: "", institution: "", year: null },
    ]);
  });

  it("edits the field name", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("field 1"), { target: { value: "ML" } });
    expect(onChange).toHaveBeenCalledWith([{ ...rows[0], field: "ML" }]);
  });

  it("edits the year via the year select", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("year 1"), { target: { value: "2020" } });
    expect(onChange).toHaveBeenCalledWith([{ ...rows[0], year: 2020 }]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<EducationEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove education 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/candidate/education-editor.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/candidate/education-editor.tsx`:

```tsx
"use client";

import type { EducationEntry } from "@specula/shared-types";
import { YearSelect } from "@/components/candidate/year-select";

const CIN =
  "w-full rounded-[6px] border border-rule bg-paper px-[10px] py-[8px] text-[12.5px] text-ink focus:border-ink focus:outline-none";

export function EducationEditor({
  value,
  onChange,
}: {
  value: EducationEntry[];
  onChange: (v: EducationEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<EducationEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () =>
    onChange([...value, { degree: "", field: "", institution: "", year: null }]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[96px_1fr_1fr_92px_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={CIN}
              placeholder="Degree"
              aria-label={`degree ${i + 1}`}
              value={row.degree}
              onChange={(e) => update(i, { degree: e.target.value })}
            />
            <input
              className={CIN}
              placeholder="Field"
              aria-label={`field ${i + 1}`}
              value={row.field}
              onChange={(e) => update(i, { field: e.target.value })}
            />
            <input
              className={CIN}
              placeholder="Institution"
              aria-label={`institution ${i + 1}`}
              value={row.institution}
              onChange={(e) => update(i, { institution: e.target.value })}
            />
            <YearSelect
              ariaLabel={`year ${i + 1}`}
              value={row.year}
              onChange={(y) => update(i, { year: y })}
            />
            <button
              type="button"
              aria-label={`remove education ${i + 1}`}
              onClick={() => remove(i)}
              className="justify-self-center font-mono text-[15px] text-ink-3 hover:text-warn"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={add}
        className="rounded-[7px] border border-dashed border-rule-2 bg-transparent px-3 py-[6px] text-[12.5px] text-ink-2 hover:border-ink hover:text-ink"
      >
        + add education
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/candidate/education-editor.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/candidate/education-editor.tsx apps/web/src/components/candidate/education-editor.test.tsx
git commit -m "feat(candidate): EducationEditor component"
```

---

### Task 8: `ProjectEditor` component

**Files:**
- Create: `apps/web/src/components/candidate/project-editor.tsx`
- Test: `apps/web/src/components/candidate/project-editor.test.tsx`

**Interfaces:**
- Consumes: `ProjectEntry` (Task 1).
- Produces: `<ProjectEditor value={ProjectEntry[]} onChange={(v) => void} />`. New rows default to `{ name: "", note: "" }`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/candidate/project-editor.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ProjectEditor } from "@/components/candidate/project-editor";

afterEach(cleanup);
const rows = [{ name: "RAG search", note: "pgvector over 2M docs" }];

describe("ProjectEditor", () => {
  it("adds a blank row", () => {
    const onChange = vi.fn();
    render(<ProjectEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add project"));
    expect(onChange).toHaveBeenCalledWith([rows[0], { name: "", note: "" }]);
  });

  it("edits the note", () => {
    const onChange = vi.fn();
    render(<ProjectEditor value={rows} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("project note 1"), { target: { value: "sub-200ms p95" } });
    expect(onChange).toHaveBeenCalledWith([{ ...rows[0], note: "sub-200ms p95" }]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<ProjectEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove project 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/candidate/project-editor.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/candidate/project-editor.tsx`:

```tsx
"use client";

import type { ProjectEntry } from "@specula/shared-types";

const CIN =
  "w-full rounded-[6px] border border-rule bg-paper px-[10px] py-[8px] text-[12.5px] text-ink focus:border-ink focus:outline-none";

export function ProjectEditor({
  value,
  onChange,
}: {
  value: ProjectEntry[];
  onChange: (v: ProjectEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<ProjectEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () => onChange([...value, { name: "", note: "" }]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[210px_1fr_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={CIN}
              placeholder="Project name"
              aria-label={`project name ${i + 1}`}
              value={row.name}
              onChange={(e) => update(i, { name: e.target.value })}
            />
            <input
              className={CIN}
              placeholder="One-line note"
              aria-label={`project note ${i + 1}`}
              value={row.note}
              onChange={(e) => update(i, { note: e.target.value })}
            />
            <button
              type="button"
              aria-label={`remove project ${i + 1}`}
              onClick={() => remove(i)}
              className="justify-self-center font-mono text-[15px] text-ink-3 hover:text-warn"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={add}
        className="rounded-[7px] border border-dashed border-rule-2 bg-transparent px-3 py-[6px] text-[12.5px] text-ink-2 hover:border-ink hover:text-ink"
      >
        + add project
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/candidate/project-editor.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/candidate/project-editor.tsx apps/web/src/components/candidate/project-editor.test.tsx
git commit -m "feat(candidate): ProjectEditor component"
```

---

### Task 9: `ExperienceEditor` component

**Files:**
- Create: `apps/web/src/components/candidate/experience-editor.tsx`
- Test: `apps/web/src/components/candidate/experience-editor.test.tsx`

**Interfaces:**
- Consumes: `ExperienceEntry` (Task 1), `YearSelect` (Task 5).
- Produces: `<ExperienceEditor value={ExperienceEntry[]} onChange={(v) => void} />`. New rows default to `{ role: "", org: "", startYear: null, endYear: null }`. End-year uses `presentLabel="Present"`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/candidate/experience-editor.test.tsx`:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ExperienceEditor } from "@/components/candidate/experience-editor";

afterEach(cleanup);
const rows = [{ role: "ML Eng", org: "Adyen", startYear: 2019, endYear: 2022 }];

describe("ExperienceEditor", () => {
  it("adds a blank row", () => {
    const onChange = vi.fn();
    render(<ExperienceEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ add role"));
    expect(onChange).toHaveBeenCalledWith([
      rows[0],
      { role: "", org: "", startYear: null, endYear: null },
    ]);
  });

  it("sets endYear to null (Present) via the end-year select", () => {
    const onChange = vi.fn();
    render(<ExperienceEditor value={rows} onChange={onChange} />);
    expect(screen.getByRole("option", { name: "Present" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("end year 1"), { target: { value: "" } });
    expect(onChange).toHaveBeenCalledWith([{ ...rows[0], endYear: null }]);
  });

  it("removes a row", () => {
    const onChange = vi.fn();
    render(<ExperienceEditor value={rows} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("remove role 1"));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/candidate/experience-editor.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/candidate/experience-editor.tsx`:

```tsx
"use client";

import type { ExperienceEntry } from "@specula/shared-types";
import { YearSelect } from "@/components/candidate/year-select";

const CIN =
  "w-full rounded-[6px] border border-rule bg-paper px-[10px] py-[8px] text-[12.5px] text-ink focus:border-ink focus:outline-none";

export function ExperienceEditor({
  value,
  onChange,
}: {
  value: ExperienceEntry[];
  onChange: (v: ExperienceEntry[]) => void;
}) {
  const update = (i: number, patch: Partial<ExperienceEntry>) =>
    onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () =>
    onChange([...value, { role: "", org: "", startYear: null, endYear: null }]);

  return (
    <div>
      <div className="mb-[9px] flex flex-col gap-2">
        {value.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[1fr_1fr_96px_96px_26px] items-center gap-2 rounded-[9px] border border-rule-2 bg-card px-[10px] py-2"
          >
            <input
              className={CIN}
              placeholder="Role"
              aria-label={`role ${i + 1}`}
              value={row.role}
              onChange={(e) => update(i, { role: e.target.value })}
            />
            <input
              className={CIN}
              placeholder="Organisation"
              aria-label={`org ${i + 1}`}
              value={row.org}
              onChange={(e) => update(i, { org: e.target.value })}
            />
            <YearSelect
              ariaLabel={`start year ${i + 1}`}
              value={row.startYear}
              onChange={(y) => update(i, { startYear: y })}
            />
            <YearSelect
              ariaLabel={`end year ${i + 1}`}
              value={row.endYear}
              presentLabel="Present"
              onChange={(y) => update(i, { endYear: y })}
            />
            <button
              type="button"
              aria-label={`remove role ${i + 1}`}
              onClick={() => remove(i)}
              className="justify-self-center font-mono text-[15px] text-ink-3 hover:text-warn"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={add}
        className="rounded-[7px] border border-dashed border-rule-2 bg-transparent px-3 py-[6px] text-[12.5px] text-ink-2 hover:border-ink hover:text-ink"
      >
        + add role
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && pnpm vitest run src/components/candidate/experience-editor.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/candidate/experience-editor.tsx apps/web/src/components/candidate/experience-editor.test.tsx
git commit -m "feat(candidate): ExperienceEditor component"
```

---

### Task 10: Extend `TagEditor` with optional suggestions

**Files:**
- Modify: `apps/web/src/components/atoms/tag-editor.tsx`
- Test: `apps/web/src/components/atoms/tag-editor.test.tsx` (append a test)

**Interfaces:**
- Produces: `TagEditor` gains an optional `suggestions?: string[]` prop; when set, the add-input is wired to a `<datalist>`. Free-add (any typed value) is unchanged. Existing call sites (no `suggestions`) are unaffected.

- [ ] **Step 1: Write the failing test (append)**

Append to `apps/web/src/components/atoms/tag-editor.test.tsx` (inside the file, after existing tests — keep existing imports; add these if missing at top: `render, screen, fireEvent, cleanup` from `@testing-library/react`, and `TagEditor`):

```tsx
describe("TagEditor suggestions", () => {
  it("wires a datalist and still accepts a free-add value not in the list", () => {
    const onChange = vi.fn();
    render(
      <TagEditor
        values={["Python"]}
        onChange={onChange}
        suggestions={["Kubernetes", "Go"]}
      />,
    );
    fireEvent.click(screen.getByText("+ add"));
    const input = document.activeElement as HTMLInputElement;
    expect(input).toHaveAttribute("list");
    const listId = input.getAttribute("list")!;
    expect(document.getElementById(listId)?.querySelectorAll("option").length).toBe(2);
    // free-add: a value NOT in suggestions is still accepted
    fireEvent.change(input, { target: { value: "Mojo" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["Python", "Mojo"]);
  });
});
```

If `vi`, `describe`, `it`, `expect`, `afterEach` are not already imported at the top of the file, add: `import { describe, it, expect, vi } from "vitest";` (the existing file already imports Testing-Library helpers and `TagEditor`).

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && pnpm vitest run src/components/atoms/tag-editor.test.tsx`
Expected: FAIL — `suggestions` prop does nothing; the input has no `list` attribute.

- [ ] **Step 3: Implement the suggestions wiring**

Edit `apps/web/src/components/atoms/tag-editor.tsx`:

First, change the React import line at the top from `import { useState } from "react";` to:

```tsx
import { useId, useState } from "react";
```

Then change the component signature and body to thread `suggestions`. Replace the `export function TagEditor({ ... }) {` destructure and the `const [adding, ...] = ...` block with:

```tsx
export function TagEditor({
  values,
  onChange,
  kind = "default",
  suggestions,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  kind?: Kind;
  suggestions?: string[];
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const listId = useId();
```

Then, in the `adding ? (` branch, add `list` to the input and render the datalist. Replace the existing `<input ... />` (the add-mode input) with:

```tsx
        <>
          <input
            autoFocus
            list={suggestions ? listId : undefined}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && commit()}
            onBlur={commit}
            className="rounded-[7px] border border-rule-2 bg-card px-3 py-[6px] text-[12.5px] text-ink outline-none focus:border-ink"
          />
          {suggestions && (
            <datalist id={listId}>
              {suggestions.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          )}
        </>
```

- [ ] **Step 4: Run to verify it passes (and existing tests still pass)**

Run: `cd apps/web && pnpm vitest run src/components/atoms/tag-editor.test.tsx`
Expected: PASS (existing tests + the new suggestions test).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/atoms/tag-editor.tsx apps/web/src/components/atoms/tag-editor.test.tsx
git commit -m "feat(tag-editor): optional datalist suggestions (free-add preserved)"
```

---

### Task 11: Integration — flip `Candidate`, wire the editors, dirty-state, actionable skills-gap

The atomic swap: change the `Candidate` interface and every consumer together so `pnpm typecheck` and Vitest end green.

**Files:**
- Modify: `packages/shared-types/src/index.ts` (change the `Candidate` interface)
- Modify: `apps/web/src/lib/api/candidate.ts` (mapping)
- Modify: `apps/web/src/lib/seed/data.ts` (candidate seed)
- Modify: `apps/web/src/components/candidate/candidate-view.tsx` (rewrite)
- Modify: `apps/web/src/components/candidate/candidate-view.test.tsx`
- Verify: `apps/web/src/lib/api/test-fixtures.ts` (should compile unchanged — it spreads the seed)

**Interfaces:**
- Consumes: all editors (Tasks 4–10), `VISA_OPTIONS`/enum types (Task 1), `COMMON_SKILLS` (Task 1), the structured API contract (Task 2).

- [ ] **Step 1: Change the `Candidate` interface**

In `packages/shared-types/src/index.ts`, replace the existing `Candidate` interface with:

```ts
export interface Candidate {
  name: string; initials: string; title: string; location: string;
  workMode: Mode[]; visa: Visa | ""; years: number;
  education: EducationEntry[]; languages: LanguageEntry[]; skills: string[];
  projects: ProjectEntry[]; experience: ExperienceEntry[];
}
```

- [ ] **Step 2: Update the API mapping (`candidate.ts`)**

Replace the entire contents of `apps/web/src/lib/api/candidate.ts` with:

```ts
import type {
  Candidate,
  EducationEntry,
  ExperienceEntry,
  LanguageEntry,
  Mode,
  ProjectEntry,
  Visa,
} from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// Shape of FastAPI's `CandidateOut` (camelCased). `candidate_profiles` has no
// name/initials/title columns — `headline` is the profile's freeform title.
type CandidateApiOut = {
  headline: string | null;
  location: string | null;
  workMode: Mode[];
  visa: Visa | null;
  years: number | null;
  education: EducationEntry[];
  languages: LanguageEntry[];
  skills: string[];
  projects: ProjectEntry[];
  experience: ExperienceEntry[];
};

// Server-side: maps the API's profile fields onto the TS `Candidate` contract.
// `name`/`initials` aren't stored server-side (the sidebar sources the display
// name from the session); they default to "".
export async function getCandidate(): Promise<Candidate> {
  const api = await bffFetch<CandidateApiOut>("/candidate");
  return {
    name: "",
    initials: "",
    title: api.headline ?? "",
    location: api.location ?? "",
    workMode: api.workMode,
    visa: api.visa ?? "",
    years: api.years ?? 0,
    education: api.education,
    languages: api.languages,
    skills: api.skills,
    projects: api.projects,
    experience: api.experience,
  };
}

// The editable subset of the candidate form, saved via `PUT /api/candidate`.
export type CandidatePatch = Omit<Candidate, "name" | "initials">;

// Client-side: persist the candidate form through the BFF route (which proxies
// to FastAPI `PUT /candidate`, a full replace). `visa: ""` (unset) maps to null.
export async function saveCandidate(patch: CandidatePatch): Promise<void> {
  const res = await fetch("/api/candidate", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      headline: patch.title,
      location: patch.location,
      workMode: patch.workMode,
      visa: patch.visa === "" ? null : patch.visa,
      years: patch.years,
      education: patch.education,
      languages: patch.languages,
      skills: patch.skills,
      projects: patch.projects,
      experience: patch.experience,
    }),
  });
  if (!res.ok) throw new Error(`Failed to save candidate (${res.status})`);
}
```

- [ ] **Step 3: Restructure the frontend seed (`data.ts`)**

In `apps/web/src/lib/seed/data.ts`, replace the `workMode`, `visa`, `education`, `languages`, and `experience` fields of the `candidate` object (leave `name`, `initials`, `title`, `location`, `years`, `skills`, `projects` as-is) so the object contains:

```ts
  workMode: ["Remote", "Hybrid", "On-site"],
  visa: "EU/EEA/Swiss citizen — no sponsorship",
```

...and (replacing the old `education:` string, `languages:` array, and `experience:` array):

```ts
  education: [
    {
      degree: "MSc",
      field: "Artificial Intelligence",
      institution: "University of Amsterdam",
      year: 2019,
    },
  ],
  languages: [
    { language: "English", level: "Native" },
    { language: "Dutch", level: "Native" },
    { language: "German", level: "B1" },
  ],
```

...and replace the `experience` array with:

```ts
  experience: [
    { role: "Senior Data Scientist", org: "Mollie", startYear: 2022, endYear: null },
    { role: "ML Engineer", org: "Adyen", startYear: 2019, endYear: 2022 },
  ],
```

- [ ] **Step 4: Update the CandidateView tests**

Replace the entire contents of `apps/web/src/components/candidate/candidate-view.test.tsx` with:

```tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CandidateView } from "@/components/candidate/candidate-view";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});

const { getCandidate } = await import("@/lib/api/candidate");
const { getSkillsGap } = await import("@/lib/api/skills-gap");

afterEach(cleanup);
const c = await getCandidate();
const gap = await getSkillsGap();

describe("CandidateView", () => {
  it("renders the profile field values", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByDisplayValue(c.title)).toBeInTheDocument();
    expect(screen.getByDisplayValue(c.location)).toBeInTheDocument();
  });

  it("renders the skills-gap panel with a gap item", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    expect(screen.getByText("Skills gap")).toBeInTheDocument();
    expect(screen.getByText(gap[0].skill)).toBeInTheDocument();
  });

  it("gates Save on dirty state", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const save = screen.getByText("Save profile");
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByDisplayValue(c.title), { target: { value: "Staff ML Engineer" } });
    expect(save).not.toBeDisabled();
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("adds a demanded skill from the skills-gap panel and drops the gap row", () => {
    render(<CandidateView candidate={c} skillsGap={gap} />);
    const target = gap[0].skill;
    fireEvent.click(screen.getByLabelText(`add ${target} to skills`));
    expect(screen.getByLabelText(`remove ${target}`)).toBeInTheDocument();
    expect(screen.queryByLabelText(`add ${target} to skills`)).toBeNull();
  });

  it("Save profile PUTs the edited fields through the BFF route", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    render(<CandidateView candidate={c} skillsGap={gap} />);

    fireEvent.change(screen.getByDisplayValue(c.title), {
      target: { value: "Staff ML Engineer" },
    });
    fireEvent.click(screen.getByText("Save profile"));
    await screen.findByText("Saved.");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/candidate",
      expect.objectContaining({ method: "PUT" }),
    );
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init!.body as string);
    expect(body.headline).toBe("Staff ML Engineer");
    expect(Array.isArray(body.workMode)).toBe(true);
    fetchMock.mockRestore();
  });
});
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd apps/web && pnpm vitest run src/components/candidate/candidate-view.test.tsx`
Expected: FAIL — the current `candidate-view.tsx` has no dirty-gating, no `add … to skills` control, and treats `workMode`/`visa` as strings (type errors / missing elements).

- [ ] **Step 6: Rewrite `candidate-view.tsx`**

Replace the entire contents of `apps/web/src/components/candidate/candidate-view.tsx` with:

```tsx
"use client";

import { useMemo, useState } from "react";
import type { Candidate, SkillsGap, Visa } from "@specula/shared-types";
import { VISA_OPTIONS } from "@specula/shared-types";
import { TagEditor } from "@/components/atoms/tag-editor";
import { Button } from "@/components/atoms/button";
import { Field } from "@/components/config/field";
import { ModeSelect } from "@/components/candidate/mode-select";
import { LanguageEditor } from "@/components/candidate/language-editor";
import { EducationEditor } from "@/components/candidate/education-editor";
import { ProjectEditor } from "@/components/candidate/project-editor";
import { ExperienceEditor } from "@/components/candidate/experience-editor";
import { COMMON_SKILLS } from "@/lib/skills-catalog";
import { saveCandidate, type CandidatePatch } from "@/lib/api/candidate";

const INPUT =
  "w-full rounded-[9px] border border-rule-2 bg-card px-[13px] py-[11px] font-body text-[13.5px] text-ink focus:border-ink focus:outline-none";

export function CandidateView({
  candidate: c,
  skillsGap,
}: {
  candidate: Candidate;
  skillsGap: SkillsGap[];
}) {
  const initial: CandidatePatch = useMemo(
    () => ({
      title: c.title,
      location: c.location,
      workMode: c.workMode,
      visa: c.visa,
      years: c.years,
      education: c.education,
      languages: c.languages,
      skills: c.skills,
      projects: c.projects,
      experience: c.experience,
    }),
    [c],
  );

  const [form, setForm] = useState<CandidatePatch>(initial);
  const [baseline, setBaseline] = useState<CandidatePatch>(initial);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const dirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(baseline),
    [form, baseline],
  );

  const set = <K extends keyof CandidatePatch>(k: K, v: CandidatePatch[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setJustSaved(false);
  };

  const hasSkill = (s: string) =>
    form.skills.some((x) => x.toLowerCase() === s.toLowerCase());
  const visibleGap = skillsGap.filter((g) => !hasSkill(g.skill));

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveCandidate(form);
      setBaseline(form);
      setJustSaved(true);
    } finally {
      setSaving(false);
    }
  };

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
            Who you are — fed to the model so every match reflects fit between you
            and the role. Kept explicit (a form, not a parsed CV) so you control
            exactly what you match against. Also powers skills-gap.
          </p>
        </div>
        <div className="flex h-[40px] w-[40px] items-center justify-center rounded-[9px] bg-ink font-mono text-[13px] font-semibold text-paper">
          {c.initials}
        </div>
      </header>

      <div className="mt-[24px] grid grid-cols-[1fr_320px] items-start gap-[26px]">
        <div>
          <Field label="Headline">
            <input
              className={INPUT}
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
            />
          </Field>
          <div className="grid grid-cols-2 gap-[16px]">
            <Field label="Location">
              <input
                className={INPUT}
                value={form.location}
                onChange={(e) => set("location", e.target.value)}
              />
            </Field>
            <Field label="Work mode">
              <ModeSelect
                value={form.workMode}
                onChange={(v) => set("workMode", v)}
              />
            </Field>
            <Field label="Years experience">
              <input
                className={INPUT}
                type="number"
                min={0}
                value={form.years}
                onChange={(e) => set("years", Number(e.target.value))}
              />
            </Field>
            <Field label="Visa">
              <select
                className={INPUT}
                value={form.visa}
                onChange={(e) => set("visa", e.target.value as Visa | "")}
              >
                <option value="">— select —</option>
                {VISA_OPTIONS.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Skills · matched against required_skills">
            <TagEditor
              values={form.skills}
              onChange={(v) => set("skills", v)}
              suggestions={COMMON_SKILLS}
            />
          </Field>

          <Field label="Projects">
            <ProjectEditor
              value={form.projects}
              onChange={(v) => set("projects", v)}
            />
          </Field>

          <Field label="Experience">
            <ExperienceEditor
              value={form.experience}
              onChange={(v) => set("experience", v)}
            />
          </Field>

          <Field label="Education">
            <EducationEditor
              value={form.education}
              onChange={(v) => set("education", v)}
            />
          </Field>

          <Field label="Languages">
            <LanguageEditor
              value={form.languages}
              onChange={(v) => set("languages", v)}
            />
          </Field>

          <div className="mt-[18px] flex items-center gap-[12px]">
            <Button variant="pri" onClick={handleSave} disabled={saving || !dirty}>
              {saving ? "Saving…" : "Save profile"}
            </Button>
            {dirty && (
              <span className="font-mono text-[11.5px] text-warn">
                Unsaved changes
              </span>
            )}
            {!dirty && justSaved && (
              <span className="text-[12.5px] text-ink-2">Saved.</span>
            )}
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
            {visibleGap.map((g) => (
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
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold">{g.skill}</div>
                  <div className="mt-px font-mono text-[10.5px] text-ink-2">
                    {g.note}
                  </div>
                </div>
                <button
                  type="button"
                  aria-label={`add ${g.skill} to skills`}
                  onClick={() => set("skills", [...form.skills, g.skill])}
                  className="rounded-[7px] border border-rule-2 bg-card px-[9px] py-[5px] text-[11px] text-accent-ink hover:border-accent hover:bg-accent-bg"
                >
                  + add
                </button>
                <span className="font-mono text-[18px] font-semibold text-warn">
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

- [ ] **Step 7: Run the CandidateView tests to verify they pass**

Run: `cd apps/web && pnpm vitest run src/components/candidate/candidate-view.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 8: Typecheck the whole web app + shared-types**

Run: `cd apps/web && pnpm typecheck && cd ../../packages/shared-types && pnpm typecheck`
Expected: both exit 0. (If `test-fixtures.ts` errors, it is only because a seed field shape is wrong — fix the seed in Step 3, do not re-loosen types.)

- [ ] **Step 9: Commit**

```bash
git add packages/shared-types/src/index.ts apps/web/src/lib/api/candidate.ts \
  apps/web/src/lib/seed/data.ts \
  apps/web/src/components/candidate/candidate-view.tsx \
  apps/web/src/components/candidate/candidate-view.test.tsx
git commit -m "feat(candidate): wire structured editors, dirty-state save, actionable skills-gap"
```

---

### Task 12: Full-suite verification + manual smoke

**Files:** none (verification only).

- [ ] **Step 1: Full typecheck**

Run: `just typecheck`
Expected: mypy (apps/api) and tsc (apps/web) both clean.

- [ ] **Step 2: Full test suite**

Run: `just up && just test`
Expected: `apps/api` pytest all pass (DB-backed tests included); `apps/web` vitest all pass.

- [ ] **Step 3: Lint/format**

Run: `just lint`
Expected: ruff (apps/api) and eslint (apps/web) clean.

- [ ] **Step 4: Migrate + reseed a clean DB**

Run: `just migrate && just seed`
Expected: both exit 0.

- [ ] **Step 5: Manual smoke of the page**

Run: `just dev-web-noauth` (starts Next with the dev auth bypass), then open `http://localhost:3000/candidate`.
Verify by hand:
- Work mode shows three toggles; toggling flips them.
- Visa is a dropdown with the four EU options.
- Projects / Experience / Education / Languages each render editable rows with `+ add` and per-row `×`; Experience/Education years are dropdowns; Experience end-year offers "Present".
- Skills "+ add" opens a typeahead; typing a common skill suggests it; a non-listed value still adds.
- The Skills-gap panel's per-row `+ add` moves the skill into Skills and removes that gap row.
- "Save profile" is disabled until an edit; editing shows "Unsaved changes"; saving shows "Saved." and re-disables.

- [ ] **Step 6: Final commit (if any lint/format fixes were applied)**

```bash
git add -A
git commit -m "chore(candidate): lint/format + verification pass"
```

---

## Self-Review

**Spec coverage** (each spec section → task):
- Work mode multi-select → Tasks 1, 4, 11. Visa enum → Tasks 1, 2, 11. Languages structured → Tasks 1, 2, 6, 11. Education structured + year select → Tasks 1, 2, 5, 7, 11. Projects editable → Tasks 8, 11. Experience structured years → Tasks 1, 2, 5, 9, 11. Skills suggestions → Tasks 1, 10, 11. Actionable skills-gap → Task 11. Dirty-state save → Task 11. Migration (3 columns + experience reshape) → Task 2. Dual-layer validation → Tasks 2 (Pydantic) + editors (frontend). Seeders → Task 3 (Python) + Task 11 (TS). Location free text / achievements deferred → honored (no tasks; Location remains a plain input in Task 11).
- No new endpoints; `upsert_candidate` untouched → holds (Task 2 changes schema/model only).

**Placeholder scan:** none — every step contains real code or a real command with expected output.

**Type consistency:** `CandidatePatch = Omit<Candidate,"name"|"initials">` is the exact shape of `form` and the `saveCandidate` argument. Editor prop names (`value`/`onChange`) are uniform. `YearSelect` (`value/onChange/ariaLabel/presentLabel`) matches its call sites in Education/Experience editors. API camelCase (`startYear`/`endYear`) ↔ DB/Pydantic snake (`start_year`/`end_year`) reconciled by `alias_generator=to_camel` + `populate_by_name=True` and `response_model` by-alias serialization. `visa: Visa | ""` (TS) ↔ `Visa | None` (API) reconciled in `getCandidate`/`saveCandidate`.
