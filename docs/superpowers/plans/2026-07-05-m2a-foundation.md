# M2a Foundation Lane — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared, serial foundation for M2 — full §4 schema + RLS, request-scoped tenant
session, Auth.js→FastAPI service-JWT bridge, the copy-me CRUD/test pattern (targeting worked
example), the shared lens-filter util, a demo seeder, and worktree-safe DB tooling.

**Architecture:** FastAPI + async SQLAlchemy 2.0 + Alembic on Postgres (pgvector/pg_trgm). Two-layer
tenancy: data-layer `user_id` scoping + Postgres RLS keyed on a per-transaction `app.user_id` GUC set
from a validated service JWT. Models become a package; one hand-written migration owns the whole
schema + RLS. See the design spec: `docs/superpowers/specs/2026-07-05-m2a-foundation-design.md`.

**Tech stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (asyncpg, NullPool), Alembic, pgvector, PyJWT,
pytest + pytest-asyncio, uv, ruff, mypy --strict.

## Global Constraints

- mypy --strict + ruff (`E,F,I,UP,B,SIM,C4,PT,RUF`, line-length 100) stay green every task.
- Do NOT modify `User`'s columns — `tests/test_models.py` asserts exactly `{id, email, name,
  google_sub, created_at}` and asserts `plan`/`stripe_customer_id` absent. Existing `tests/test_db.py`
  (raw `asyncio.run` + `migrated_db` + manual rollback) must keep passing.
- No count columns anywhere; no salary on `targeting`; `scores` has no `factor_loc`/overall `match`;
  `postings` has no `raw_snapshot_key` (keep `content_hash` + `source_url`). No billing anywhere.
- Client never sends `user_id`. Services scope by `user_id` AND rely on the RLS backstop.
- Services never `commit()`/`rollback()` — the `get_session` dependency owns the transaction.
- pgvector columns are nullable and left NULL this lane (embeddings are a later lane).
- All DB-integration tests are guarded so the suite still passes without Postgres (reuse the existing
  `requires_db` skip pattern from `tests/test_db.py`, or the async equivalent).

---

### Task 1: Tooling, config, and models-package conversion

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/specula_api/config.py`
- Create: `apps/api/specula_api/db/columns.py`
- Convert: `apps/api/specula_api/db/models.py` → package `apps/api/specula_api/db/models/` with
  `__init__.py` + `user.py`
- Test: `apps/api/tests/test_models.py` (existing — must still pass unchanged)

**Interfaces produced:** `from specula_api.db.models import User` still works; `db.columns` exports
`uuid_pk`, `user_fk`, `TimestampMixin`, `Vector1536`.

- [ ] **Step 1: Add dependencies + pytest asyncio mode.** In `pyproject.toml` add runtime deps
  `"pgvector>=0.3"`, `"pyjwt>=2.9"` to `[project].dependencies`; add `"pytest-asyncio>=0.24"` to
  `[dependency-groups].dev`; add under `[tool.pytest.ini_options]`: `asyncio_mode = "auto"`. Run
  `cd apps/api && uv sync`.

- [ ] **Step 2: Extend config.** In `config.py` add to `Settings`:
  ```python
  service_jwt_secret: str = ""
  service_jwt_issuer: str = "specula-web"
  service_jwt_audience: str = "specula-api"
  ```

- [ ] **Step 3: Create `db/columns.py`** — shared column helpers (keep mypy --strict clean):
  ```python
  import uuid
  from datetime import datetime

  from pgvector.sqlalchemy import Vector
  from sqlalchemy import ForeignKey, func, text
  from sqlalchemy.dialects.postgresql import UUID
  from sqlalchemy.orm import Mapped, mapped_column

  Vector1536 = Vector(1536)

  def uuid_pk() -> Mapped[uuid.UUID]:
      return mapped_column(UUID(as_uuid=True), primary_key=True,
                           server_default=text("gen_random_uuid()"))

  def user_fk(*, primary_key: bool = False, index: bool = True) -> Mapped[uuid.UUID]:
      return mapped_column(UUID(as_uuid=True),
                           ForeignKey("users.id", ondelete="CASCADE"),
                           primary_key=primary_key, index=index and not primary_key)

  class TimestampMixin:
      updated_at: Mapped[datetime] = mapped_column(
          server_default=func.now(), onupdate=func.now())
  ```
  (Confirm `pgvector` ships `py.typed`; if mypy --strict complains, add a narrow `# type: ignore` on
  the import only — never disable strict globally.)

- [ ] **Step 4: Convert models to a package.** Delete `db/models.py`; create `db/models/user.py`
  containing the EXACT current `User` class (unchanged columns); create `db/models/__init__.py`:
  ```python
  from specula_api.db.models.user import User

  __all__ = ["User"]
  ```
  (Later tasks append imports here as they add model modules — `env.py`'s
  `from specula_api.db import models` picks them all up via this package.)

- [ ] **Step 5: Verify** — `cd apps/api && uv run pytest tests/test_models.py tests/test_db.py -q`
  (all pass; `User` unchanged), then `uv run mypy .` and `uv run ruff check`. Expected: green.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "chore(api): deps + config + models package for M2 (M2a)"`

---

### Task 2: The §4 SQLAlchemy models

**Files:**
- Create: `apps/api/specula_api/db/models/{candidate_profile,targeting,lens,company,posting,score,posting_state,approval,run,skills_taxonomy,user_settings}.py`
- Modify: `apps/api/specula_api/db/models/__init__.py` (import + re-export each)
- Test: `apps/api/tests/test_schema_models.py` (new — metadata-level, no DB)

**Interfaces produced:** all table classes importable from `specula_api.db.models`; each per-user
table has a `user_id` column; `skills_taxonomy` has none.

- [ ] **Step 1: Write the failing metadata test** (`tests/test_schema_models.py`) asserting the
  contract — table set present on `Base.metadata.tables`, every per-user table has `user_id`,
  `skills_taxonomy` does not, and the invariant columns are ABSENT:
  ```python
  from specula_api.db.base import Base

  PER_USER = {"candidate_profiles","targeting","user_settings","lenses","companies",
              "postings","scores","posting_state","approvals","runs"}

  def test_all_tables_registered() -> None:
      names = set(Base.metadata.tables)
      assert PER_USER | {"users","skills_taxonomy"} <= names

  def test_per_user_tables_have_user_id() -> None:
      for t in PER_USER:
          assert "user_id" in Base.metadata.tables[t].columns

  def test_global_table_has_no_user_id() -> None:
      assert "user_id" not in Base.metadata.tables["skills_taxonomy"].columns

  def test_invariants_no_forbidden_columns() -> None:
      assert "raw_snapshot_key" not in Base.metadata.tables["postings"].columns
      score_cols = set(Base.metadata.tables["scores"].columns.keys())
      assert {"factor_loc","match","overall"}.isdisjoint(score_cols)
      assert not any(c for c in Base.metadata.tables["targeting"].columns if "salary" in c.name)
      for t in ("lenses","companies"):
          assert "count" not in Base.metadata.tables[t].columns
  ```
  Run: `uv run pytest tests/test_schema_models.py -q` → FAIL (tables missing).

- [ ] **Step 2: Implement the models**, one module per table, following the §4 field lists in the
  design spec and using `db/columns.py` helpers. Column-type conventions: text arrays
  `mapped_column(ARRAY(Text), server_default=text("'{}'"))`; jsonb
  `mapped_column(JSONB, server_default=text("'[]'"))` (or `'{}'` for object stores); confidence/int
  fields `Integer`; booleans `mapped_column(Boolean, server_default=text("false"))`; vectors
  `mapped_column(Vector1536, nullable=True)`. 1:1 tables (`candidate_profiles`, `targeting`,
  `user_settings`) use `user_id` as PK via `user_fk(primary_key=True)`. `scores`/`posting_state` use
  `posting_id` PK (`ForeignKey("postings.id", ondelete="CASCADE")`) AND carry an indexed `user_id`
  (needed for the RLS predicate). `postings.company_id` → `ForeignKey("companies.id",
  ondelete="SET NULL")`, nullable. Enforce the invariants structurally (omit the forbidden columns).
  Re-export each class from `db/models/__init__.py`.

- [ ] **Step 3: Run the test** → `uv run pytest tests/test_schema_models.py -q` → PASS. Then
  `uv run mypy .` + `uv run ruff check` → green.

- [ ] **Step 4: Commit** — `git commit -am "feat(api): §4 SQLAlchemy models (M2a)"`

---

### Task 3: The M2 migration + RLS

**Files:**
- Create: `apps/api/alembic/versions/<hash>_m2_schema_and_rls.py` (generate the stub with
  `cd apps/api && uv run alembic revision -m "m2 schema and rls"`, then hand-write; set
  `down_revision = "c712fb8e0bd1"`)
- Test: `apps/api/tests/test_migration_m2.py` (new; `requires_db`-guarded)

**Interfaces produced:** `alembic upgrade head` builds the entire §4 schema with RLS forced on the 10
per-user tables.

- [ ] **Step 1: Write the failing DB test** (guarded like `tests/test_db.py`) — after
  `migrated_db`, assert a representative table exists and RLS is forced:
  ```python
  @requires_db
  def test_m2_schema_and_rls(migrated_db: None) -> None:
      async def check() -> None:
          async with engine.connect() as conn:
              assert (await conn.execute(sa.text(
                  "select to_regclass('public.lenses')"))).scalar() == "lenses"
              forced = (await conn.execute(sa.text(
                  "select relforcerowsecurity from pg_class where relname='lenses'"))).scalar()
              assert forced is True
              ext = (await conn.execute(sa.text(
                  "select count(*) from pg_extension where extname in ('vector','pg_trgm')"))).scalar()
              assert ext == 2
      asyncio.run(check())
  ```
  Run → FAIL (tables/extensions absent).

- [ ] **Step 2: Hand-write the migration.** `upgrade()`: `op.execute("CREATE EXTENSION IF NOT EXISTS
  vector")` + `pg_trgm`; `op.create_table(...)` for all §4 tables in FK order (candidate_profiles,
  targeting, user_settings, lenses, companies, postings, scores, posting_state, approvals, runs,
  skills_taxonomy) mirroring the model columns; add `unique(user_id, domain)` on companies,
  `unique(user_id, content_hash)` on postings, the per-`user_id` indexes, the partial
  `approvals(user_id) WHERE decision IS NULL`, and the ivfflat index
  `CREATE INDEX ... ON postings USING ivfflat (skills_vec vector_cosine_ops) WITH (lists = 100)`;
  then the RLS loop:
  ```python
  PER_USER = ["candidate_profiles","targeting","user_settings","lenses","companies",
              "postings","scores","posting_state","approvals","runs"]
  for t in PER_USER:
      op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
      op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
      op.execute(f"""CREATE POLICY tenant_isolation ON {t}
          USING (user_id = current_setting('app.user_id', true)::uuid)
          WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)""")
  # users: enable but DO NOT force (auth path looks up by google_sub before app.user_id is set)
  op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
  op.execute("""CREATE POLICY users_self ON users
      USING (id = current_setting('app.user_id', true)::uuid)""")
  ```
  `downgrade()`: drop tables in reverse FK order (policies drop with tables); leave extensions.

- [ ] **Step 3: Verify** — `cd apps/api && uv run alembic upgrade head` (against `just up` Postgres)
  then `uv run pytest tests/test_migration_m2.py -q` → PASS; `uv run mypy .` (alembic excluded) +
  `uv run ruff check`. Confirm `uv run alembic downgrade base && uv run alembic upgrade head`
  round-trips clean.

- [ ] **Step 4: Commit** — `git commit -am "feat(api): M2 schema + RLS migration (M2a)"`

---

### Task 4: Async test harness + RLS cross-tenant backstop

**Files:**
- Modify: `apps/api/tests/conftest.py` (add async fixtures + helpers; keep `migrated_db`)
- Create: `apps/api/tests/test_rls.py`

**Interfaces produced:** `db_session` (rollback-isolated `AsyncSession`), `set_tenant(session, uid)`,
`make_user(session)` — reused by every DB test in this lane and the fan-out lanes.

- [ ] **Step 1: Add fixtures/helpers to `conftest.py`** (guarded so no-DB still skips):
  ```python
  import uuid
  from collections.abc import AsyncGenerator

  import pytest_asyncio
  from sqlalchemy import text
  from sqlalchemy.ext.asyncio import AsyncSession

  from specula_api.db.models import User
  from specula_api.db.session import engine

  @pytest_asyncio.fixture
  async def db_session(migrated_db: None) -> AsyncGenerator[AsyncSession, None]:
      async with engine.connect() as conn:
          trans = await conn.begin()
          session = AsyncSession(bind=conn, expire_on_commit=False,
                                 join_transaction_mode="create_savepoint")
          try:
              yield session
          finally:
              await session.close()
              await trans.rollback()

  async def set_tenant(session: AsyncSession, user_id: uuid.UUID) -> None:
      await session.execute(
          text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id)))

  async def make_user(session: AsyncSession) -> User:
      u = User(email=f"{uuid.uuid4()}@example.com", google_sub=str(uuid.uuid4()))
      session.add(u); await session.flush(); return u
  ```

- [ ] **Step 2: Write the cross-tenant backstop test** (`tests/test_rls.py`) — the proof that FORCE
  RLS works:
  ```python
  from sqlalchemy import select
  from specula_api.db.models import Targeting
  from tests.conftest import set_tenant, make_user  # or fixtures

  async def test_user_a_cannot_see_user_b_rows(db_session):
      a = await make_user(db_session); b = await make_user(db_session)
      await set_tenant(db_session, a.id)
      db_session.add(Targeting(user_id=a.id, role_titles=["ML Eng"]))
      await db_session.flush()
      await set_tenant(db_session, b.id)
      rows = (await db_session.scalars(select(Targeting))).all()
      assert rows == []
      await set_tenant(db_session, a.id)
      assert len((await db_session.scalars(select(Targeting))).all()) == 1
  ```

- [ ] **Step 3: Verify** — `uv run pytest tests/test_rls.py -q` → PASS (and confirm it FAILS if
  `FORCE` is removed, to prove the test is real). mypy + ruff green.

- [ ] **Step 4: Commit** — `git commit -am "test(api): async DB harness + RLS cross-tenant backstop (M2a)"`

---

### Task 5: Request-scoped tenant session + pgvector codec

**Files:**
- Modify: `apps/api/specula_api/db/session.py` (register the pgvector asyncpg codec on connect)
- Create: `apps/api/specula_api/deps.py` (`get_session`)
- Test: `apps/api/tests/test_session_guc.py`

**Interfaces produced:** `get_session` FastAPI dependency (depends on `get_current_user_id`, added in
Task 6 — for now depend on a small `get_current_user_id` placeholder that Task 6 replaces; OR order
Task 6 before this. Recommended: keep this task's `get_session` parameterized by a `user_id` provided
via `Depends(get_current_user_id)` and land Task 6 first if simpler).

- [ ] **Step 1: Register the pgvector codec** in `session.py`:
  ```python
  from pgvector.asyncpg import register_vector
  from sqlalchemy import event

  @event.listens_for(engine.sync_engine, "connect")
  def _register_vector(dbapi_conn, _):  # type: ignore[no-untyped-def]
      dbapi_conn.run_async(register_vector)
  ```

- [ ] **Step 2: Write `get_session`** in `deps.py` (owns the transaction; sets the GUC first):
  ```python
  async def get_session(
      user_id: UUID = Depends(get_current_user_id),
  ) -> AsyncGenerator[AsyncSession, None]:
      async with async_session() as session:
          await session.execute(
              text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id)))
          try:
              yield session
              await session.commit()
          except Exception:
              await session.rollback()
              raise
  ```

- [ ] **Step 3: Write the test** — mount a throwaway route on a fresh `FastAPI()` that overrides
  `get_current_user_id` to a fixed uuid, uses `get_session`, and returns
  `current_setting('app.user_id')`; assert it equals the uuid. Also assert two requests with
  different override uuids don't leak (NullPool). Guarded by `requires_db`.

- [ ] **Step 4: Verify** — `uv run pytest tests/test_session_guc.py -q` → PASS; mypy + ruff green.

- [ ] **Step 5: Commit** — `git commit -am "feat(api): tenant-scoped session + app.user_id GUC + pgvector codec (M2a)"`

---

### Task 6: Auth bridge — service-JWT validation + user provisioning

**Files:**
- Create: `apps/api/specula_api/auth.py` (`ServiceClaims`, `decode_service_jwt`, a `mint` test helper)
- Modify: `apps/api/specula_api/deps.py` (`get_current_user_id`)
- Test: `apps/api/tests/test_auth.py`

**Interfaces produced:** `get_current_user_id` (FastAPI dependency reading `Authorization: Bearer`),
consumed by `get_session`. Service-JWT claim contract: HS256, `secret=service_jwt_secret`,
`iss=specula-web`, `aud=specula-api`, `sub=google_sub`, `email`/`name`, TTL 60s.

- [ ] **Step 1: Write failing tests** (`tests/test_auth.py`): a valid minted token decodes to the
  expected `ServiceClaims`; an expired token and a wrong-`aud` token raise (→ 401 at the dep);
  `get_current_user_id` find-or-creates a `User` by `google_sub` idempotently (two calls, same uuid).
  Use a `mint(sub, email, name, ttl=60)` helper in `auth.py` for tests + the future web side.

- [ ] **Step 2: Implement `auth.py`** — `ServiceClaims(BaseModel)` (`sub`, `email`, `name|None`);
  `decode_service_jwt(token)` (`jwt.decode(..., algorithms=["HS256"], audience=..., issuer=...,
  leeway=5)` → `ServiceClaims`); `mint(...)` (`jwt.encode`, sets `iss`/`aud`/`iat`/`exp`).

- [ ] **Step 3: Implement `get_current_user_id`** in `deps.py` — read `Authorization` header
  (`Header(...)`), strip `Bearer `, `decode_service_jwt` (raise `HTTPException(401)` on any
  `jwt`/validation error), then on an UNSCOPED `async_session()` (users not force-RLS'd)
  find-or-create by `google_sub` (handle the concurrent-first-request `IntegrityError` → re-select),
  return `user.id`.

- [ ] **Step 4: Verify** — `uv run pytest tests/test_auth.py -q` → PASS; mypy + ruff green.

- [ ] **Step 5: Commit** — `git commit -am "feat(api): service-JWT auth bridge + user provisioning (M2a)"`

---

### Task 7: Worked example — targeting CRUD end-to-end (the copy-me template)

**Files:**
- Create: `apps/api/specula_api/schemas/{__init__.py,targeting.py}`
- Create: `apps/api/specula_api/services/{__init__.py,targeting.py}`
- Create: `apps/api/specula_api/routers/{__init__.py,targeting.py}`
- Modify: `apps/api/specula_api/main.py` (include `api_router`)
- Test: `apps/api/tests/test_targeting_api.py`

**Interfaces produced:** `api_router = APIRouter(prefix="/api/v1")`; `GET/PUT /api/v1/targeting`; the
schema/service/router pattern every fan-out lane clones.

- [ ] **Step 1: Write failing end-to-end tests** (`tests/test_targeting_api.py`, `requires_db`) using
  `httpx.AsyncClient(transport=ASGITransport(app=create_app()))` with `Authorization: Bearer
  {mint(sub=...)}`: (a) `GET /api/v1/targeting` for a fresh user returns empty defaults; (b) `PUT`
  with a body persists and echoes it (camelCase keys — `roleTitles`, `mustHaves`); (c) a second
  user's `GET` never sees the first user's data (cross-tenant through the real HTTP + RLS path).

- [ ] **Step 2: Implement the schema** (`schemas/targeting.py`) — camelCase base
  (`alias_generator=to_camel`, `populate_by_name=True`), `TargetingIn` (role_titles, seniority,
  must_haves, avoid, preferences), `TargetingOut(TargetingIn)` (`from_attributes=True`, +
  `updated_at`). Never expose `user_id`.

- [ ] **Step 3: Implement the service** (`services/targeting.py`) — `get_targeting(session, user_id)`
  (`session.get(Targeting, user_id)`) and `upsert_targeting(session, user_id, data)` (get-or-create,
  `setattr` on update, `flush()`, return row). No commit.

- [ ] **Step 4: Implement the router + wiring** — `routers/targeting.py` (`GET`/`PUT`, both
  `Depends(get_current_user_id)` + `Depends(get_session)`); `routers/__init__.py` builds
  `api_router = APIRouter(prefix="/api/v1")` and `include_router(targeting.router)`; `main.py`
  `create_app()` calls `app.include_router(api_router)`.

- [ ] **Step 5: Verify** — `uv run pytest tests/test_targeting_api.py -q` → PASS; full
  `uv run pytest -q` + mypy + ruff green.

- [ ] **Step 6: Commit** — `git commit -am "feat(api): targeting GET/PUT + base CRUD pattern (M2a)"`

---

### Task 8: Shared lens-filter util

**Files:**
- Create: `apps/api/specula_api/services/lens_filter.py`
- Test: `apps/api/tests/test_lens_filter.py`

**Interfaces produced:** `lens_where(lens) -> list[ColumnElement[bool]]` — SQLAlchemy predicates over
`postings ⋈ companies` for a lens's `scope`/`modes`/`origin_rule`; imported by the lenses lane
(counts) and jobs lane (pool). Port exact semantics from `apps/web/src/lib/seed/logic.ts`
(`filterByLens`).

- [ ] **Step 1: Write failing unit tests** (`tests/test_lens_filter.py`, `requires_db` + seeded rows
  via `db_session`): a Foreign-HQ lens returns only postings where `hq_country <> country`; a
  modes-limited lens returns only matching `work_mode`; the default `All` lens returns everything;
  a scope-limited lens filters by location.

- [ ] **Step 2: Implement `lens_where`** — read `apps/web/src/lib/seed/logic.ts` `filterByLens` for
  the exact rules, translate to SQLAlchemy conditions (`Posting.hq_country != Posting.country` for
  `origin_rule == "foreign_hq"`, `Posting.work_mode.in_(lens.modes)` when modes non-empty, scope →
  location match; `is_default`/`All` → no conditions). Pure function; no DB access inside.

- [ ] **Step 3: Verify** — `uv run pytest tests/test_lens_filter.py -q` → PASS; mypy + ruff green.

- [ ] **Step 4: Commit** — `git commit -am "feat(api): shared lens-filter predicate util (M2a)"`

---

### Task 9: Demo seeder + just recipes + env

**Files:**
- Create: `apps/api/specula_api/seed.py`
- Modify: `justfile` (add recipes)
- Modify: `.env.example` (service-JWT + per-worktree DB note)
- Test: `apps/api/tests/test_seed.py`

**Interfaces produced:** `python -m specula_api.seed` (idempotent demo data); `just migrate` / `seed` /
`db-bootstrap <db>` recipes.

- [ ] **Step 1: Write the seeder** (`seed.py`) — an async `main()` using `async_session()` directly:
  find-or-create the demo user (fixed `google_sub`/`email=demo@specula.app`), `set_config` the GUC to
  the demo uuid, delete the demo user's per-user rows (RLS-scoped) for idempotent reseed, then insert:
  candidate_profile + targeting + default `All` lens + one scoped lens + a few companies + ~13
  postings (port from `apps/web/src/lib/seed/data.ts`, include ONE low-confidence posting) + scores +
  posting_state on several + a couple approvals (decision null) + one run + user_settings + a couple
  GLOBAL `skills_taxonomy` rows (outside the tenant scope). `*_vec` left NULL. Guard entry with
  `if __name__ == "__main__": asyncio.run(main())`.

- [ ] **Step 2: Write the test** (`tests/test_seed.py`, `requires_db`) — running the seeder twice
  leaves exactly one demo user and a stable row count (idempotent), and the low-confidence posting
  exists. (Run against the shared dev DB or a throwaway; keep it `requires_db`-guarded.)

- [ ] **Step 3: Add `just` recipes:**
  ```make
  migrate:
      cd apps/api && uv run alembic upgrade head
  migrate-down rev="-1":
      cd apps/api && uv run alembic downgrade {{rev}}
  migration name:
      cd apps/api && uv run alembic revision -m "{{name}}"
  seed:
      cd apps/api && uv run python -m specula_api.seed
  db-create db="specula":
      docker compose exec -T postgres psql -U specula -d specula -c "CREATE DATABASE {{db}}" || true
  db-bootstrap db="specula":
      just db-create {{db}}
      DATABASE_URL="postgresql+asyncpg://specula:specula@localhost:5432/{{db}}" just migrate
      DATABASE_URL="postgresql+asyncpg://specula:specula@localhost:5432/{{db}}" just seed
  ```

- [ ] **Step 4: Update `.env.example`** — add `SERVICE_JWT_SECRET=` (shared web+api HS256 secret) with
  a comment, and a note that each git worktree overrides `DATABASE_URL` to its own
  `…/specula_wt_<lane>` DB.

- [ ] **Step 5: Verify** — `just up` then `just db-bootstrap specula` (or `just migrate && just seed`)
  succeeds; `uv run pytest -q` (full suite) + mypy + ruff green.

- [ ] **Step 6: Commit** — `git commit -am "feat(api): demo seeder + migrate/seed/db-bootstrap recipes (M2a)"`

---

## Final verification (whole lane)

After Task 9: `just up`, `just db-bootstrap specula`, then `cd apps/api && uv run pytest -q`
(all green, DB tests exercised), `uv run mypy .`, `uv run ruff check`. Confirm the RLS cross-tenant
test genuinely fails when `FORCE` is stripped (proves the backstop). Then a whole-branch code review
(superpowers:requesting-code-review) before merging to `main`.

## Self-review notes

- Task 5 depends on Task 6's `get_current_user_id`; if simpler, execute Task 6 before Task 5 (the
  session GUC test can mint a real token instead of overriding the dep).
- `pgvector` + mypy --strict: if no `py.typed`, isolate the ignore to the import line.
- Every DB-integration test is `requires_db`-guarded so CI without Postgres still passes; the CI web
  job already has no DB — decide in Task 3/9 whether to add a Postgres service to the API CI job or
  keep DB tests skip-on-CI (recommend: add the pgvector service to the api CI job so RLS is actually
  exercised — the api job already runs Postgres for pytest per `.github/workflows/ci.yml`).
