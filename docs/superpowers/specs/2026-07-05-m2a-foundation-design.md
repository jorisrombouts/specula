# M2a — Foundation Lane: Design Spec

**Status:** approved (2026-07-05). Serial, first slice of M2; everything else in M2 branches from it.

## Goal

Lay the shared, serial foundation for M2 "Persistence & tenancy": the full §4 database schema with
Row-Level Security, the request-scoped tenant session, the Auth.js→FastAPI service-JWT bridge, the
copy-me CRUD/test patterns (one worked example), a demo seeder, and the worktree-safe DB tooling —
so the parallel fan-out CRUD lanes can each build one clean vertical against a stable base.

## Why serial / why first

The schema + the single Alembic migration + RLS + the auth bridge + the base patterns are shared,
linear state. Every fan-out lane imports the models this creates and clones the worked example. Two
worktrees authoring migrations concurrently would collide. So this lane is built and merged to `main`
before any fan-out worktree is created.

## Architecture (resolved decisions)

- **Models** become a package `apps/api/specula_api/db/models/` (one file per table; `__init__.py`
  re-exports `User` so `from specula_api.db.models import User` and `alembic/env.py`'s
  `from specula_api.db import models` keep working). `db/columns.py` holds shared helpers
  (`uuid_pk()`, `user_fk()`, `TimestampMixin`, `Vector1536 = Vector(1536)`).
- **One hand-written migration** (`down_revision="c712fb8e0bd1"`): `CREATE EXTENSION vector, pg_trgm`;
  all §4 tables in FK order; unique/partial/ivfflat indexes; and RLS — `ENABLE` + **`FORCE ROW LEVEL
  SECURITY`** + policy `USING (user_id = current_setting('app.user_id', true)::uuid) WITH CHECK (…)`
  on the 10 per-user tables. `FORCE` is required because the app connects as table owner (owners
  bypass RLS otherwise) and it's what makes the cross-tenant test real. `users` gets RLS enabled but
  **not forced** (self-policy) so the auth path can look users up by `google_sub` before
  `app.user_id` is set. `--autogenerate` is NOT used (can't emit extensions/ivfflat/partial/RLS).
- **Tenant session** (`deps.py` `get_session`): open `AsyncSession`; first statement
  `SELECT set_config('app.user_id', :uid, true)` (transaction-scoped GUC, asyncpg-safe via
  bindparams; NullPool → fresh connection per request, no leakage). **The dependency owns the
  transaction; services never `commit()`/`rollback()`** (a mid-request commit drops the `SET LOCAL`
  GUC). `session.py` also registers the pgvector asyncpg codec on connect.
- **Auth bridge (FastAPI side)** (`auth.py` + `deps.py` `get_current_user_id`): validate
  `Authorization: Bearer <jwt>` (HS256; verify `exp`/`iss`/`aud`, ~5s leeway), find-or-create the
  user by `google_sub` on an unscoped session (idempotent sign-in bootstrap, spec §9), return the
  internal uuid. **Service-JWT contract (web + api must agree):** alg HS256, secret
  `SERVICE_JWT_SECRET`, `iss=specula-web`, `aud=specula-api`, `sub=google_sub`, `email`/`name` for
  provisioning, TTL 60s. `config.py` gains `service_jwt_secret/issuer/audience`.
- **Base per-resource pattern — worked example `targeting` (1:1 PUT)**, built end-to-end as the
  template: `schemas/targeting.py` (camelCase via `alias_generator=to_camel`, never expose
  `user_id`) → `services/targeting.py` (function-per-operation, scoped by explicit `user_id`,
  `flush()` not `commit()`) → `routers/targeting.py` (`GET`/`PUT`) → `test_targeting_api.py`.
  `routers/__init__.py` builds `api_router = APIRouter(prefix="/api/v1")`; `main.py` includes it.
  **No generic CRUD base** (YAGNI; fights mypy --strict).
- **Shared lens-filter util** (`services/lens_filter.py`): translate a lens
  (`scope`/`modes`/`origin_rule`) into SQLAlchemy conditions over `postings ⋈ companies` (e.g.
  Foreign-HQ = `postings.hq_country <> postings.country`). Foundation-owned because both the lenses
  lane (counts) and the jobs lane (pool) need it — removes an inter-lane dependency. Port semantics
  from `apps/web/src/lib/seed/logic.ts`.
- **Test harness**: adopt `pytest-asyncio` (`asyncio_mode="auto"`, backward-compatible with the
  existing raw-`asyncio.run` tests); `db_session` fixture bound to a connection-level transaction with
  `join_transaction_mode="create_savepoint"` (code `commit()`s become savepoint releases; outer txn
  rolls back at teardown → zero residue); `set_tenant`/`make_user` helpers; `test_rls.py` cross-tenant
  backstop. Per-worktree DB isolation via a `DATABASE_URL` env override.
- **Demo seeder** (`specula_api/seed.py`, `python -m specula_api.seed`): idempotent; find-or-create
  demo user, set the GUC, seed the three config verticals + default+scoped lens + companies + ~13
  postings (port from `apps/web/src/lib/seed/data.ts`) + scores + posting_state on several + a couple
  approvals + a run + user_settings + a couple global `skills_taxonomy` rows; include **one
  low-confidence posting**. Leave `*_vec` NULL.
- **New `just` recipes**: `migrate` / `migrate-down` / `migration` (hand-edit) / `seed` / `db-create`
  / `db-bootstrap <db>`.

## Global constraints (bind every task)

- **mypy --strict** + **ruff** (`E,F,I,UP,B,SIM,C4,PT,RUF`, line-length 100) must stay green.
- **Product invariants, enforced structurally:** no count columns anywhere (counts derived at read
  time); no salary fields on `targeting`; `scores` stores only `factor_role`/`factor_skill`/overlap/
  `red_flag`/`rationale`/`scored_with`/`scored_at` (no `factor_loc`, no overall `match`); low-confidence
  postings excluded from Insights (schema carries `extraction_confidence`); **no object storage** —
  `postings` keeps `content_hash` + `source_url`, drops `raw_snapshot_key`.
- **Do not modify `User`'s columns** — `tests/test_models.py` asserts the exact 5-column set and the
  absence of `plan`/`stripe_customer_id`. `user_settings` is a separate table, not User columns.
- **No billing** anywhere (no Stripe, plan tiers, entitlements).
- Client never sends `user_id`; every per-user query is scoped in the data layer **and** guarded by
  RLS (two layers).

## Out of scope (deferred)

Fan-out CRUD lanes (lenses/candidate/companies/jobs+state/insights/approvals/tweaks), the Next-side
service-JWT minter + frontend fetch swap (Frontend-wiring lane), real embeddings (`*_vec` stay NULL),
and all M3/M4 pipeline behavior (crawl/extract/score). Two-role least-privilege RLS hardening is
deferred (single owner + FORCE now); flagged for pre-prod.
