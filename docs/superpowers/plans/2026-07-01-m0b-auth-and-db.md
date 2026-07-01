# Specula M0b — Auth (Google) & DB Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google sign-in (Auth.js v5, JWT session) gating the web shell, and a database foundation in the API (async SQLAlchemy 2.0 + Alembic + a first migration creating the `users` table) — two independent halves that meet only in M2.

**Architecture:** Web: NextAuth v5 with the Google provider and a stateless JWT session; the `(app)` route group is protected by an async server guard in its layout (`await auth()` → redirect to `/signin`); the sidebar shows the session identity + sign-out. API: an async SQLAlchemy engine/session + a `User` model + Alembic (async env) with a first migration, run against local docker Postgres; the DB integration test skips when Postgres is unreachable and runs in CI via a Postgres service container.

**Tech Stack:** Next.js 16 · React 19 · next-auth@5 (Auth.js) · TypeScript strict · Vitest + Playwright · Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Alembic · asyncpg · Postgres (pgvector/pgvector:pg16) · uv · pnpm.

## Global Constraints

Apply to **every** task. Sources: `docs/superpowers/specs/2026-07-01-m0b-auth-and-db-design.md`, `docs/Specula - Design Spec.md` §4/§8/§9/§17, `CLAUDE.md`.

- **Working directory:** repo root is `/Users/jorisrombouts/Projects/Personal/specula`. Run web commands from `apps/web`, api commands from `apps/api` (or `just …` from root). Branch is **main** (work directly on main — no branch).
- **Two independent halves.** The web→api bootstrap, BFF **signed service-JWT**, **RLS**/`app.user_id`, and the **full domain schema** are all **M2** — do not build them. Build nothing speculative (YAGNI).
- **No billing (deviation):** the `users` table omits `plan` and `stripe_customer_id` (spec §4.1 listed them).
- **Google-only auth.** No email magic-link provider. The user provisions real Google OAuth creds **later** — so **no test may depend on a real Google round-trip**; tests use the unauthenticated redirect path and mocked sessions/modules.
- **`users` columns (exact):** `id` uuid PK default `gen_random_uuid()`; `email` **citext** unique not null; `name` text nullable; `google_sub` text unique not null; `created_at` timestamptz default `now()`. Enable the `citext` extension in the migration.
- **DB dev target:** local docker Postgres (`just up`). `DATABASE_URL` uses the async driver form `postgresql+asyncpg://…`. Neon is a deploy-time swap (not provisioned now).
- **Session strategy = JWT (stateless).** No NextAuth DB adapter; FastAPI stays the single DB owner. `session.user.id` is exposed from `token.sub`.
- **DB test gating:** the API DB integration test **auto-skips** when `DATABASE_URL` is unreachable (so `just test` is green offline), and **runs in CI** (Postgres service) and locally after `just up`.
- Quality gates stay green: `just lint`, `just typecheck`, `just test`, `just e2e`, `pre-commit run --all-files`. ruff + mypy --strict cover new Python; ESLint + Prettier + tsc cover new TS. Vitest `include` is `src/**/*.test.{ts,tsx}`; Playwright is `e2e/**`.
- **Pre-commit hooks are installed.** Web commits run `pnpm lint && pnpm format:check`; api commits run ruff/ruff-format/mypy. Keep new files clean so commits don't bounce.

---

## File Structure

```
apps/api/
  pyproject.toml                         # MODIFY (T1) deps; (T2) mypy exclude alembic
  specula_api/
    config.py                            # MODIFY (T1) database_url → +asyncpg
    db/__init__.py                       # CREATE (T1)
    db/base.py                           # CREATE (T1) Base(DeclarativeBase)
    db/session.py                        # CREATE (T1) async engine + async_sessionmaker
    db/models.py                         # CREATE (T1) User
  tests/test_models.py                   # CREATE (T1) no-DB metadata test
  alembic.ini                            # CREATE (T2) via `alembic init -t async`
  alembic/env.py                         # CREATE+MODIFY (T2) async env → settings + metadata
  alembic/script.py.mako                 # CREATE (T2) generated
  alembic/versions/<hash>_create_users.py# CREATE (T2) first migration
  tests/conftest.py                      # CREATE (T2) migrated_db fixture (schema upgrade)
  tests/test_db.py                       # CREATE (T2) skip-marker + migration + round-trip + uniqueness

apps/web/
  src/auth.ts                            # CREATE (T3) NextAuth config
  src/app/api/auth/[...nextauth]/route.ts# CREATE (T3) handlers
  src/components/google-sign-in-button.tsx# CREATE (T3) client button
  src/components/google-sign-in-button.test.tsx # CREATE (T3) Vitest
  src/app/signin/page.tsx                # CREATE (T3) sign-in page
  src/types/next-auth.d.ts               # CREATE (T3) session.user.id augmentation
  .env.local                             # CREATE (T3) gitignored dummy AUTH_SECRET (local dev/e2e)
  src/app/(app)/layout.tsx               # MODIFY (T4) async guard + pass user
  src/components/sidebar.tsx             # MODIFY (T4) user prop + identity + sign-out
  src/components/sidebar.test.tsx        # MODIFY (T4) user prop + sign-out
  src/components/view-shell.test.tsx     # CREATE (T4) preserve label coverage
  e2e/shell.spec.ts                      # REWRITE (T4) unauth redirect + signin button

.env.example                             # MODIFY (T5) auth vars + async DATABASE_URL
.github/workflows/ci.yml                 # MODIFY (T5) api Postgres service + web dummy auth env
CLAUDE.md                                # MODIFY (T5) note Google-only + JWT + local-DB
```

---

### Task 1: API DB foundation — engine, session, User model

**Files:**
- Modify: `apps/api/pyproject.toml`, `apps/api/specula_api/config.py`
- Create: `apps/api/specula_api/db/__init__.py`, `db/base.py`, `db/session.py`, `db/models.py`, `apps/api/tests/test_models.py`

**Interfaces:**
- Produces: `specula_api.db.base.Base` (DeclarativeBase); `specula_api.db.session.engine` (AsyncEngine), `specula_api.db.session.async_session` (async_sessionmaker); `specula_api.db.models.User` (table `users`, columns `id/email/name/google_sub/created_at`). Consumed by Task 2 (alembic + tests).
- Consumes: `specula_api.config.settings.database_url`.

- [ ] **Step 1: Add dependencies**

In `apps/api/pyproject.toml`, extend `[project].dependencies` (keep existing fastapi/uvicorn/pydantic/pydantic-settings):
```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "asyncpg>=0.29",
]
```
Then:
```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/api && uv sync
```
Expected: `uv.lock` updated; sqlalchemy/alembic/asyncpg (+ greenlet) installed.

- [ ] **Step 2: Point `database_url` at the async driver**

Replace the `database_url` line in `apps/api/specula_api/config.py`:
```python
    database_url: str = "postgresql+asyncpg://specula:specula@localhost:5432/specula"
```

- [ ] **Step 3: Write the failing metadata test**

`apps/api/tests/test_models.py`:
```python
from specula_api.db.models import User


def test_user_table_name() -> None:
    assert User.__tablename__ == "users"


def test_user_has_exactly_the_expected_columns() -> None:
    cols = {c.name for c in User.__table__.columns}
    assert cols == {"id", "email", "name", "google_sub", "created_at"}


def test_user_email_and_google_sub_are_unique() -> None:
    assert User.__table__.c.email.unique is True
    assert User.__table__.c.google_sub.unique is True


def test_user_has_no_billing_columns() -> None:
    cols = {c.name for c in User.__table__.columns}
    assert "plan" not in cols
    assert "stripe_customer_id" not in cols
```

- [ ] **Step 4: Run it to verify it fails**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/api && uv run pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'specula_api.db'`.

- [ ] **Step 5: Create the db package — base + session**

```bash
mkdir -p apps/api/specula_api/db
touch apps/api/specula_api/db/__init__.py
```
`apps/api/specula_api/db/base.py`:
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```
`apps/api/specula_api/db/session.py`:
```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from specula_api.config import settings

engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 6: Write the `User` model**

`apps/api/specula_api/db/models.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    name: Mapped[str | None] = mapped_column(String, default=None)
    google_sub: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 7: Run the test + quality gate**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/api
uv run pytest tests/test_models.py -v
uv run ruff check && uv run ruff format --check && uv run mypy .
```
Expected: 4 tests PASS; ruff clean; format clean; `mypy: Success`. (No DB needed — this is metadata only.) If mypy flags the SQLAlchemy `Mapped`/`mapped_column` usage, ensure `sqlalchemy>=2.0` resolved (2.0 ships native typing). If `ruff format` reports diffs, run `uv run ruff format` and re-check.

- [ ] **Step 8: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/api
git commit -m "feat(api): async SQLAlchemy engine/session and User model"
```

---

### Task 2: API Alembic + first migration + DB integration tests

**Files:**
- Create: `apps/api/alembic.ini`, `apps/api/alembic/env.py`, `apps/api/alembic/script.py.mako`, `apps/api/alembic/versions/<hash>_create_users.py`, `apps/api/tests/conftest.py`, `apps/api/tests/test_db.py`
- Modify: `apps/api/pyproject.toml` (mypy exclude for `alembic/`)

**Interfaces:**
- Consumes: `Base`, `User`, `engine`, `async_session` (Task 1); `settings.database_url`.
- Produces: an applied `users` table via `alembic upgrade head`; the DB integration test suite (skip-gated).

- [ ] **Step 1: Scaffold Alembic (async template)**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/api
uv run alembic init -t async alembic
```
Expected: creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`.

- [ ] **Step 2: Point Alembic at our settings URL + model metadata**

Edit `apps/api/alembic/env.py`: (a) add imports of our settings + metadata near the top after the existing imports; (b) override the URL; (c) set `target_metadata`. Concretely, add after `config = context.config`:
```python
from specula_api.config import settings  # noqa: E402
from specula_api.db import models  # noqa: E402, F401  (register models on Base.metadata)
from specula_api.db.base import Base  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.database_url)
```
and replace the generated `target_metadata = None` line with:
```python
target_metadata = Base.metadata
```
(Leave the async `run_async_migrations`/`do_run_migrations` machinery the template generated.)

- [ ] **Step 3: Exclude `alembic/` from mypy strict**

In `apps/api/pyproject.toml` under `[tool.mypy]`, add an exclude (Alembic's generated env/migrations are not strict-clean):
```toml
[tool.mypy]
strict = true
python_version = "3.12"
exclude = ["^alembic/"]
```

- [ ] **Step 4: Generate an empty first-migration file, then fill it in**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/api
uv run alembic revision -m "create_users"
```
This writes `alembic/versions/<hash>_create_users.py`. Replace its `upgrade`/`downgrade` bodies with:
```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("google_sub", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_sub"),
    )


def downgrade() -> None:
    op.drop_table("users")
```
Ensure the migration's imports include `from alembic import op`, `import sqlalchemy as sa`, and `from sqlalchemy.dialects import postgresql` (add the postgresql import if the template didn't). Keep the generated `revision`/`down_revision` header lines untouched.

- [ ] **Step 5: Apply the migration locally (proves it works)**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
just up   # start docker Postgres if not running
cd apps/api && uv run alembic upgrade head
uv run alembic downgrade base   # verify reversibility
uv run alembic upgrade head     # leave schema at head
```
Expected: upgrade runs without error and creates `users`; downgrade drops it; re-upgrade recreates it. (If `just up` isn't possible in this environment, report the exact error — the DB half needs Postgres.)

- [ ] **Step 6: Write the DB reachability gate + fixture (`conftest.py`)**

`apps/api/tests/conftest.py` (only the `migrated_db` fixture — pytest auto-injects fixtures by name, so no cross-file import is needed; the skip marker lives in `test_db.py`):
```python
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[None]:
    command.upgrade(Config("alembic.ini"), "head")
    yield
```

- [ ] **Step 7: Write the DB integration tests (`test_db.py`)**

`apps/api/tests/test_db.py` (defines its own skip marker locally — no import from conftest):
```python
import asyncio
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from specula_api.db.models import User
from specula_api.db.session import async_session, engine


def _db_reachable() -> bool:
    async def check() -> bool:
        try:
            async with engine.connect():
                return True
        except Exception:
            return False

    try:
        return asyncio.run(check())
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_reachable(), reason="Postgres not reachable (run `just up`)"
)


@requires_db
def test_migration_creates_users_table(migrated_db: None) -> None:
    async def check() -> str | None:
        async with engine.connect() as conn:
            result = await conn.execute(sa.text("select to_regclass('public.users')"))
            value = result.scalar()
            return str(value) if value is not None else None

    assert asyncio.run(check()) == "users"


@requires_db
def test_user_round_trip(migrated_db: None) -> None:
    async def run() -> None:
        async with async_session() as session:
            user = User(
                email=f"{uuid.uuid4()}@example.com",
                google_sub=str(uuid.uuid4()),
                name="Test User",
            )
            session.add(user)
            await session.flush()
            fetched = await session.get(User, user.id)
            assert fetched is not None
            assert fetched.name == "Test User"
            await session.rollback()

    asyncio.run(run())


@requires_db
def test_duplicate_email_violates_unique(migrated_db: None) -> None:
    async def run() -> None:
        shared = f"{uuid.uuid4()}@example.com"
        async with async_session() as session:
            session.add(User(email=shared, google_sub=str(uuid.uuid4())))
            session.add(User(email=shared, google_sub=str(uuid.uuid4())))
            try:
                await session.flush()
                raise AssertionError("expected IntegrityError on duplicate email")
            except IntegrityError:
                await session.rollback()

    asyncio.run(run())
```

- [ ] **Step 8: Run the tests + quality gate (with Postgres up)**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/api
uv run pytest -v
uv run ruff check && uv run ruff format --check && uv run mypy .
```
Expected: `test_health`, `test_models`, and the 3 `test_db` tests PASS (5+ passing). ruff clean; `mypy: Success` (alembic excluded). Then confirm the **skip** path works with Postgres down:
```bash
cd /Users/jorisrombouts/Projects/Personal/specula && just down
cd apps/api && uv run pytest tests/test_db.py -v
```
Expected: the 3 `test_db` tests **SKIP** ("Postgres not reachable"); exit code 0. Then `cd .. && just up` to restore.

- [ ] **Step 9: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/api
git commit -m "feat(api): Alembic first migration (users) and DB integration tests"
```

---

### Task 3: Web — Auth.js core, sign-in page, Google button

**Files:**
- Create: `apps/web/src/auth.ts`, `apps/web/src/app/api/auth/[...nextauth]/route.ts`, `apps/web/src/components/google-sign-in-button.tsx`, `apps/web/src/components/google-sign-in-button.test.tsx`, `apps/web/src/app/signin/page.tsx`, `apps/web/src/types/next-auth.d.ts`, `apps/web/.env.local`

**Interfaces:**
- Produces: `auth`, `handlers`, `signIn`, `signOut` from `@/auth`; `<GoogleSignInButton/>`; the `/signin` route; the `Session.user.id` type augmentation. Consumed by Task 4 (guard + sidebar).

- [ ] **Step 1: Install next-auth v5**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm add next-auth@beta
```
Expected: `next-auth` (v5, "@beta" is the v5 channel) added to `dependencies`; lockfile updated.

- [ ] **Step 2: Create a local dummy `AUTH_SECRET` (gitignored) for dev/e2e**

`apps/web/.env.local`:
```
AUTH_SECRET=dev-dummy-secret-not-for-production
```
(Confirm it's ignored: `git check-ignore apps/web/.env.local` prints the path. The root `.gitignore` `.env.*` covers it. Real Google creds are added here by the user later; without them the Google round-trip won't complete, which does not block the guard, `/signin`, or any test.)

- [ ] **Step 3: Write the NextAuth config (`src/auth.ts`)**

`apps/web/src/auth.ts`:
```ts
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
  pages: { signIn: "/signin" },
  callbacks: {
    session({ session, token }) {
      if (session.user && token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
  },
});
```
(The Google provider auto-reads `AUTH_GOOGLE_ID`/`AUTH_GOOGLE_SECRET`; `AUTH_SECRET` signs the JWT.)

- [ ] **Step 4: Session type augmentation (`src/types/next-auth.d.ts`)**

`apps/web/src/types/next-auth.d.ts`:
```ts
import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: { id: string } & DefaultSession["user"];
  }
}
```

- [ ] **Step 5: The auth route handler**

`apps/web/src/app/api/auth/[...nextauth]/route.ts`:
```ts
import { handlers } from "@/auth";

export const { GET, POST } = handlers;
```

- [ ] **Step 6: Write the failing test for the Google button**

`apps/web/src/components/google-sign-in-button.test.tsx`:
```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

const signIn = vi.fn();
vi.mock("next-auth/react", () => ({ signIn }));

afterEach(() => {
  cleanup();
  signIn.mockClear();
});

describe("GoogleSignInButton", () => {
  it("renders a 'Sign in with Google' button", async () => {
    const { GoogleSignInButton } = await import(
      "@/components/google-sign-in-button"
    );
    render(<GoogleSignInButton />);
    expect(
      screen.getByRole("button", { name: /sign in with google/i }),
    ).toBeInTheDocument();
  });

  it("calls signIn('google') on click", async () => {
    const { GoogleSignInButton } = await import(
      "@/components/google-sign-in-button"
    );
    render(<GoogleSignInButton />);
    fireEvent.click(screen.getByRole("button", { name: /sign in with google/i }));
    expect(signIn).toHaveBeenCalledWith("google", { redirectTo: "/jobs" });
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test
```
Expected: FAIL — `Failed to resolve import "@/components/google-sign-in-button"`.

- [ ] **Step 8: Implement the button + sign-in page**

`apps/web/src/components/google-sign-in-button.tsx`:
```tsx
"use client";

import { signIn } from "next-auth/react";

export function GoogleSignInButton() {
  return (
    <button
      type="button"
      onClick={() => signIn("google", { redirectTo: "/jobs" })}
      className="font-body rounded-[7px] border border-rule-2 bg-card px-4 py-[9px] text-[13px] font-medium text-ink transition-colors hover:border-ink"
    >
      Sign in with Google
    </button>
  );
}
```
`apps/web/src/app/signin/page.tsx`:
```tsx
import { GoogleSignInButton } from "@/components/google-sign-in-button";

export default function SignInPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-paper">
      <div className="flex flex-col items-center gap-1">
        <span className="font-display text-[34px] font-semibold tracking-[0.02em] text-ink">
          Specula
        </span>
        <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-3">
          role ledger
        </span>
      </div>
      <GoogleSignInButton />
    </main>
  );
}
```

- [ ] **Step 9: Run the test + quality gate**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm test
pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```
Expected: the 2 new Vitest tests pass (plus the existing suites; the M0a sidebar test still passes — it's untouched this task); lint/tsc clean; `pnpm build` succeeds and lists `/signin` + the `/api/auth/[...nextauth]` route. (Build reads `AUTH_SECRET` from `.env.local`.) Run `pnpm format` if `format:check` flags files.

- [ ] **Step 10: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web
git commit -m "feat(web): Auth.js v5 Google provider, sign-in page, and Google button"
```

---

### Task 4: Web — route guard, sidebar identity + sign-out, test updates

**Files:**
- Modify: `apps/web/src/app/(app)/layout.tsx`, `apps/web/src/components/sidebar.tsx`, `apps/web/src/components/sidebar.test.tsx`, `apps/web/e2e/shell.spec.ts`
- Create: `apps/web/src/components/view-shell.test.tsx`

**Interfaces:**
- Consumes: `auth` from `@/auth` (Task 3); `signOut` from `next-auth/react`; `NAV`/`isActive` from `@/lib/nav`.
- Produces: the guarded `(app)` shell; `Sidebar({ user })` where `user: { name?: string | null; email?: string | null }`.

- [ ] **Step 1: Add the guard to `(app)/layout.tsx`**

Replace `apps/web/src/app/(app)/layout.tsx` (entire file):
```tsx
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { Sidebar } from "@/components/sidebar";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.user) redirect("/signin");
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <Sidebar user={session.user} />
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Update the failing sidebar test first (identity + sign-out)**

Replace `apps/web/src/components/sidebar.test.tsx` (entire file):
```tsx
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

const signOut = vi.fn();
vi.mock("next-auth/react", () => ({ signOut }));

const USER = { name: "Ada Lovelace", email: "ada@example.com" };

afterEach(() => {
  cleanup();
  signOut.mockClear();
});

function mockPath(pathname: string) {
  vi.doMock("next/navigation", () => ({ usePathname: () => pathname }));
}

describe("Sidebar", () => {
  beforeEach(() => vi.resetModules());

  it("renders the brand, all six nav items, and the signed-in identity", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
    expect(screen.getByText("Specula")).toBeInTheDocument();
    for (const label of [
      "Jobs",
      "Approval queue",
      "Companies",
      "Insights",
      "Search profiles",
      "Targeting",
    ]) {
      expect(
        screen.getByRole("link", { name: new RegExp(label, "i") }),
      ).toBeInTheDocument();
    }
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
  });

  it("marks exactly the current route active via aria-current", async () => {
    mockPath("/companies");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
    const active = screen
      .getAllByRole("link")
      .filter((el) => el.getAttribute("aria-current") === "page");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveAccessibleName(/companies/i);
  });

  it("fabricates no counts — renders no digit badges in the nav", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    const { container } = render(<S user={USER} />);
    expect(container.querySelector("nav")?.textContent ?? "").not.toMatch(/\d/);
  });

  it("renders the Refresh button as inert (disabled)", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
    expect(screen.getByRole("button", { name: /refresh/i })).toBeDisabled();
  });

  it("signs out on clicking Sign out", async () => {
    mockPath("/jobs");
    const { Sidebar: S } = await import("@/components/sidebar");
    render(<S user={USER} />);
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(signOut).toHaveBeenCalledWith({ redirectTo: "/signin" });
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/components/sidebar.test.tsx
```
Expected: FAIL — `Sidebar` doesn't accept `user`, doesn't render the identity, and has no Sign out button yet.

- [ ] **Step 4: Update `sidebar.tsx` — accept `user`, show identity, add sign-out**

In `apps/web/src/components/sidebar.tsx`: (a) add `"use client"` stays; add imports; (b) change the signature; (c) replace the candidate-card block. Full new file:
```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { NAV, isActive, type NavItem } from "@/lib/nav";
import { Icon } from "@/components/icon";

type SidebarUser = { name?: string | null; email?: string | null };

export function Sidebar({ user }: { user: SidebarUser }) {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col overflow-hidden border-r border-rule bg-panel">
      {/* Brand + inert sync/refresh */}
      <div className="border-b border-rule px-5 pb-4 pt-[22px]">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-[23px] font-semibold tracking-[0.05em] text-ink">
            Specula
          </span>
          <span className="font-mono text-[10px] tracking-[0.02em] text-ink-2">
            role ledger
          </span>
        </div>
        <div className="mt-[14px] flex flex-col gap-[9px]">
          <div className="font-mono flex items-center gap-2 text-[11px] text-ink-2">
            <span className="sync-dot relative h-[7px] w-[7px] flex-shrink-0 rounded-full bg-accent" />
            synced <b className="font-semibold text-ink">—</b> ·{" "}
            <b className="font-semibold text-ink">—</b> new
          </div>
          <button
            type="button"
            disabled
            title="Available in a later milestone"
            className="font-body mt-1 flex w-full items-center justify-center gap-[7px] rounded-[7px] bg-ink px-3 py-[9px] text-[12.5px] font-semibold text-paper opacity-60"
          >
            <span aria-hidden>↻</span> Refresh now
          </button>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-[14px_12px]">
        {NAV.map((entry, i) =>
          "section" in entry ? (
            <div
              key={`s${i}`}
              className="font-mono px-[10px] pb-[7px] pt-[14px] text-[9.5px] uppercase tracking-[0.16em] text-ink-3"
            >
              {entry.section}
            </div>
          ) : (
            <NavLink
              key={(entry as NavItem).id}
              item={entry as NavItem}
              pathname={pathname}
            />
          ),
        )}
      </nav>

      {/* Signed-in identity + sign-out */}
      <div className="flex flex-col gap-2 border-t border-rule p-3">
        <Link
          href="/candidate"
          aria-current={isActive("/candidate", pathname) ? "page" : undefined}
          className={`flex w-full items-center gap-[11px] rounded-[9px] border px-[10px] py-[9px] text-left ${
            isActive("/candidate", pathname)
              ? "border-rule bg-panel-2"
              : "border-transparent hover:border-rule hover:bg-panel-2"
          }`}
        >
          <span className="font-mono flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-[9px] bg-ink text-paper">
            <span className="h-[15px] w-[15px]">
              <Icon name="candidate" />
            </span>
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-semibold text-ink">
              {user.name ?? "Account"}
            </span>
            <span className="block truncate text-[11.5px] text-ink-2">
              {user.email ?? ""}
            </span>
          </span>
        </Link>
        <button
          type="button"
          onClick={() => signOut({ redirectTo: "/signin" })}
          className="font-mono w-full rounded-[7px] px-[10px] py-[6px] text-left text-[10.5px] uppercase tracking-[0.1em] text-ink-3 hover:bg-panel-2 hover:text-ink"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const on = isActive(item.href, pathname);
  return (
    <Link
      href={item.href}
      aria-current={on ? "page" : undefined}
      className={`flex items-center gap-[10px] rounded-lg px-[11px] py-[9px] text-[13.5px] font-medium ${
        on ? "bg-ink text-paper" : "text-ink-2 hover:bg-panel-2 hover:text-ink"
      }`}
    >
      <span className="flex h-[15px] w-[15px] flex-shrink-0">
        <Icon name={item.icon} />
      </span>
      <span className="flex-1">{item.label}</span>
    </Link>
  );
}
```

- [ ] **Step 5: Run the sidebar test to verify it passes**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web && pnpm test src/components/sidebar.test.tsx
```
Expected: all 5 sidebar cases PASS (identity shown, one aria-current, no nav digits, refresh disabled, sign-out calls `signOut`).

- [ ] **Step 6: Add the ViewShell label test (preserve route-label coverage)**

`apps/web/src/components/view-shell.test.tsx`:
```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ViewShell } from "@/components/view-shell";

afterEach(cleanup);

describe("ViewShell", () => {
  it("renders its screen-label, title, and sub", () => {
    const { container } = render(
      <ViewShell label="jobs" title="Jobs" sub="The pool of roles." />,
    );
    expect(container.querySelector('[data-screen-label="jobs"]')).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Jobs" })).toBeInTheDocument();
    expect(screen.getByText("The pool of roles.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Rewrite the E2E suite for the guard (unauth redirect + sign-in)**

Replace `apps/web/e2e/shell.spec.ts` (entire file) — the M0a cases assumed open `(app)` routes; under the guard they redirect. Cover the guard + sign-in page (cred-free):
```ts
import { test, expect } from "@playwright/test";

test("an unauthenticated visit to an app route redirects to sign-in", async ({
  page,
}) => {
  await page.goto("/jobs");
  await expect(page).toHaveURL(/\/signin$/);
});

test("the root redirects an unauthenticated user to sign-in", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/signin$/);
});

test("the sign-in page renders on warm paper with a Google button", async ({
  page,
}) => {
  await page.goto("/signin");
  const bg = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  // --paper #FBFAF6 == rgb(251, 250, 246)
  expect(bg).toBe("rgb(251, 250, 246)");
  await expect(
    page.getByRole("button", { name: /sign in with google/i }),
  ).toBeVisible();
});
```

- [ ] **Step 8: Run the full web suite + gates**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/apps/web
pnpm test
pnpm test:e2e
pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```
Expected: Vitest all green (nav + sidebar + button + view-shell); Playwright 3/3 green (both redirects + the sign-in page). (`pnpm dev` for Playwright reads `AUTH_SECRET` from `.env.local`, so `auth()` returns null → redirect.) lint/tsc/build clean.

- [ ] **Step 9: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add apps/web
git commit -m "feat(web): protect the app shell behind Google auth; sidebar identity + sign-out"
```

---

### Task 5: Env, CI (Postgres service + auth env), and docs

**Files:**
- Modify: `.env.example`, `.github/workflows/ci.yml`, `CLAUDE.md`

**Interfaces:**
- Consumes: the api DB tests (Task 2) and web auth (Tasks 3–4) — CI must provide Postgres (for the api integration tests to run) and a dummy `AUTH_SECRET` (so the web build + Playwright don't fail on missing auth env).

- [ ] **Step 1: Document env vars in `.env.example`**

Replace `.env.example` (entire file):
```bash
# Specula environment. Copy to .env and fill in. New vars are added per milestone.
APP_ENV=development

# Postgres (local docker via `just up`). Async driver form for SQLAlchemy/asyncpg.
DATABASE_URL=postgresql+asyncpg://specula:specula@localhost:5432/specula

# Auth.js (web). AUTH_SECRET signs the session JWT — generate with `npx auth secret`.
# AUTH_GOOGLE_ID / AUTH_GOOGLE_SECRET come from a Google Cloud OAuth client
# (provisioned later; sign-in only completes once these are real).
AUTH_SECRET=
AUTH_GOOGLE_ID=
AUTH_GOOGLE_SECRET=
```

- [ ] **Step 2: Give the CI `api` job a Postgres service + DATABASE_URL**

In `.github/workflows/ci.yml`, replace the `api:` job (through its steps) so it has a Postgres service and the pytest step sees it. The new `api` job:
```yaml
  api:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: specula
          POSTGRES_PASSWORD: specula
          POSTGRES_DB: specula
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U specula -d specula"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    defaults:
      run:
        working-directory: apps/api
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --frozen
      - run: uv run ruff check
      - run: uv run ruff format --check
      - run: uv run mypy .
      - run: uv run pytest
        env:
          DATABASE_URL: postgresql+asyncpg://specula:specula@localhost:5432/specula
```

- [ ] **Step 3: Give the CI `web` job a dummy `AUTH_SECRET`**

In the `web:` job, add a job-level `env` block (so `pnpm build` and Playwright's `pnpm dev` have it). Insert directly under `web:` `runs-on: ubuntu-latest`:
```yaml
  web:
    runs-on: ubuntu-latest
    env:
      AUTH_SECRET: ci-dummy-secret-not-for-production
    defaults:
      run:
        working-directory: apps/web
    steps:
      # …existing steps unchanged…
```
(Keep all existing web steps: install → lint → typecheck → format:check → build → test → playwright install → test:e2e.)

- [ ] **Step 4: Validate the CI YAML**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
pre-commit run check-yaml --files .github/workflows/ci.yml
```
Expected: `check-yaml` passes.

- [ ] **Step 5: Note the M0b decisions in `CLAUDE.md`**

In `apps/web`… no — the repo-root `CLAUDE.md`. Under "## Stack & hosting (free-tier first)", append a line:
```markdown
- Auth: Auth.js v5 (NextAuth), **Google-only** sign-in, **JWT (stateless) session** — no DB adapter;
  FastAPI owns the DB. Dev DB = local docker Postgres (`just up`); Neon is a deploy-time DATABASE_URL swap.
  DB access is async SQLAlchemy 2.0 + Alembic (first migration = `users`, identity only).
```

- [ ] **Step 6: Run the full local gate**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
just up
just lint && just typecheck && just test && just e2e
pre-commit run --all-files
```
Expected: all green — api (health + models + 3 db tests) and web (vitest + playwright) pass; pre-commit clean.

- [ ] **Step 7: Commit**

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git add .env.example .github/workflows/ci.yml CLAUDE.md
git commit -m "chore: env docs, CI Postgres service + auth env, CLAUDE.md notes"
```
(The controller pushes to `main` and watches CI after the final whole-branch review.)

---

## Self-Review

**1. Spec coverage** (design spec §1–§7):
- §1 web-half: Auth.js Google + JWT (T3 `auth.ts`); route protection (T4 layout guard); `/signin` page (T3); sidebar identity + sign-out (T4). §1 api-half: async SQLAlchemy engine/session/model (T1); Alembic + first migration = `users` only, no billing, citext (T2); local docker DB + CI Postgres service (T2 local, T5 CI).
- §2 web files all mapped (auth.ts, route, signin, button, layout, sidebar, next-auth.d.ts). §3 api files all mapped (config, db/*, alembic, migration, tests). §4 data flow: JWT cookie, no DB write on login, halves don't call each other — respected (no bootstrap/service-JWT built). §5 error handling: unauth→redirect (T4); missing AUTH_SECRET documented (T1 env note / T3 .env.local / T5 .env.example); DB-unreachable skip (T2 conftest). §6 testing: Vitest button+sidebar+viewshell, Playwright unauth-redirect+signin, api skip-gated integration, CI Postgres + dummy auth env — all present. §7 acceptance 1–7 map to T4 (redirect/signin), T3 (provider wiring), T4 (identity/sign-out), T2 (users table), T2/T5 (skip+CI), T5 (gates/env/CLAUDE).
- Deviations: no billing → T1 model + T1 metadata test asserts absence. Google-only → no email provider anywhere. Deferred (bootstrap/service-JWT/RLS/full schema/Neon) → not built. **All covered.**

**2. Placeholder scan:** No "TBD"/"add validation"/"similar to". Every code step shows full file contents or an exact anchored edit. The `<hash>` in the migration filename is Alembic-generated (Step 4 generates it, then fills the body) — not a plan placeholder. The E2E rewrite is given in full (not "update the tests").

**3. Type consistency:** `Base`/`engine`/`async_session`/`User` (T1) are the exact names imported by T2 (env.py, conftest, test_db). `auth`/`handlers`/`signIn`/`signOut` from `@/auth` (T3) match T3's route + T4's layout/sidebar imports. `Sidebar({ user })` with `user: { name?: string | null; email?: string | null }` (T4) matches the layout's `<Sidebar user={session.user} />` and the test's `USER` object. `signIn("google", { redirectTo: "/jobs" })` and `signOut({ redirectTo: "/signin" })` are consistent between the components and their tests. `session.user.id = token.sub` (T3 callback) matches the `next-auth.d.ts` augmentation. `ViewShell({ label, title, sub })` (existing) matches the new T4 test. **Consistent.**
