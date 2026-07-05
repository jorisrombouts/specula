-- Runs ONCE on a fresh volume, as the bootstrap superuser, before the app connects.
--
-- Why this exists: the postgres image's bootstrap role (POSTGRES_USER=specula) is a
-- SUPERUSER, and superusers bypass Row-Level Security unconditionally — so `FORCE ROW
-- LEVEL SECURITY` on the tenant tables would be silently inert and the tenancy
-- backstop would be fake. Postgres also forbids removing SUPERUSER from the bootstrap
-- role, so we can't just downgrade it. Instead we create a separate, non-superuser
-- role — `specula_app` — that OWNS the schema and is what the app, migrations, seeder,
-- and tests all connect as. RLS/FORCE then actually applies to it. This mirrors prod
-- (Neon roles are never superusers), where the app likewise connects as a plain
-- non-superuser owner. The bootstrap superuser is used only here, at init.
--
-- `vector` (pgvector) is NOT a trusted extension, so a non-superuser can't create it;
-- we pre-create it (and the trusted pg_trgm/citext) here as the superuser. The Alembic
-- migrations' idempotent `CREATE EXTENSION IF NOT EXISTS` then no-op cleanly under the
-- non-superuser role.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE ROLE specula_app LOGIN PASSWORD 'specula' NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE specula TO specula_app;
-- specula_app creates (and therefore owns) every table via the migrations, so FORCE
-- RLS applies to it on the tenant tables while it still owner-bypasses the (enabled,
-- not-forced) `users` table for the sign-in provisioning lookup.
GRANT CREATE, USAGE ON SCHEMA public TO specula_app;
