# Specula M0b — Auth (Google) & DB Foundations: Design Spec

> **Status:** approved design, ready for `writing-plans`.
> **Milestone:** M0b (second half of spec §18 "M0 — Foundations"). M0a (web shell) is done. This
> completes M0's remaining items: **Auth.js login** and **Neon + first Alembic migration**.
> **Sources of truth:** `docs/Specula - Design Spec.md` §4 (data model), §8 (API/BFF/service-JWT),
> §9 (auth/tenancy/billing), §17 (envs/secrets), §18 (roadmap). `CLAUDE.md` (deviations/invariants).
> **Conflict rule:** architecture/behavior → production spec wins; visuals → prototype wins.

---

## 1. Goal & boundary

Add the two foundational subsystems M0a didn't: **Google sign-in** on the web app (gating the
shell) and the **database + migration harness** on the API (async SQLAlchemy 2.0 + Alembic + the
first migration). The two halves are built **independently** and meet only in M2.

After M0b: a user must sign in with Google to reach the app shell; the signed-in identity shows in
the sidebar and sign-out works; and `apps/api` has an async DB layer with a first migration that
creates the `users` table against Postgres.

**In scope (M0b):**

*Web half — Google login:*
1. Auth.js v5 (NextAuth) with the **Google provider**, **JWT (stateless) session** — no DB adapter.
2. Route protection: the whole `(app)` group requires a session; unauthenticated → `/signin`.
3. A public `/signin` page with a "Sign in with Google" button.
4. Sign-out + real identity: the sidebar candidate card shows the **session user** (name/email) and
   hosts the sign-out control.

*API half — DB foundations:*
5. Async SQLAlchemy 2.0 engine + session, Alembic (async env), a `User` model.
6. **First migration** = the `users` table only (identity; **no billing columns**), enabling `citext`.
7. Wire the DB against **local docker Postgres** for dev; CI gets a Postgres service container.

**Out of scope (deferred, with the milestone that owns it):**
- **Bootstrap-on-sign-in** (web → api upsert of the `users` row), the **BFF signed service-JWT**,
  **RLS** / `app.user_id`, and the **full domain schema** (candidate_profiles, targeting, lenses,
  companies, postings, scores, posting_state, approvals, runs, skills_taxonomy) → **M2**.
- **Email magic-link** provider → dropped (Google-only for now; the spec listed both, we chose Google).
- **Neon provisioning** → deploy time (Neon is a `DATABASE_URL` swap; §17). Dev uses docker Postgres.
- Any real product data, API endpoints beyond `/health`, or UI beyond the shell → M1/M2.

**Deviations honored** (`CLAUDE.md`): **no billing** — the `users` table omits `plan` and
`stripe_customer_id` (spec §4.1 had them). No object storage (irrelevant here).

**Reality of Google creds:** the user provisions the Google OAuth credentials **later**. M0b **wires**
the provider (reads creds from env); the actual Google round-trip only completes once real creds
exist. Therefore **no test depends on a real Google login** — tests use the unauthenticated path
(redirect to `/signin`) and mocked sessions.

---

## 2. Web half — Auth.js (NextAuth v5), Google, JWT session

### 2.1 Files

```
apps/web/
  auth.ts                                   # CREATE — NextAuth config: Google provider, jwt session;
                                            #   exports { handlers, auth, signIn, signOut }
  src/app/api/auth/[...nextauth]/route.ts   # CREATE — export const { GET, POST } = handlers
  src/app/signin/page.tsx                   # CREATE — public sign-in page (Google button)
  src/app/(app)/layout.tsx                  # MODIFY — async guard: await auth(); redirect if no session;
                                            #   pass session.user to <Sidebar/>
  src/components/sidebar.tsx                # MODIFY — accept `user` prop; render name/email; sign-out
  src/lib/sign-out-action.ts               # CREATE — "use server" action wrapping signOut()
  src/types/next-auth.d.ts                  # CREATE — session/user type augmentation (user.id = token.sub)
```
(No `middleware.ts` — the `(app)/layout.tsx` server guard is the protection mechanism, not edge middleware.)

### 2.2 Auth config (`auth.ts`)

- `NextAuth({ providers: [Google], session: { strategy: "jwt" }, pages: { signIn: "/signin" } })`.
- The **Google provider** auto-reads `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` (Auth.js v5 env
  convention). `AUTH_SECRET` signs the session cookie/JWT.
- `callbacks.jwt` persists the Google account `sub` onto the token; `callbacks.session` exposes
  `session.user.id = token.sub`. (Identity carried in the cookie — no DB.)
- Exports `handlers` (for the route), `auth` (server-side session read), `signIn`, `signOut`.

### 2.3 Route protection (layout guard)

`(app)/layout.tsx` becomes an **async server component**:
```
const session = await auth();
if (!session?.user) redirect("/signin");
return <div class="grid …"><Sidebar user={session.user} /><main>…</main></div>;
```
Because every screen is under `(app)`, this single guard protects the entire app. `/` still
redirects to `/jobs` (→ guarded). `/signin` is outside `(app)` → public.

### 2.4 Sign-in page (`/signin`)

Public, editorial-styled (paper, Spectral wordmark) — a centered card with a **"Sign in with
Google"** button. The button submits a `<form action={…}>` that calls `signIn("google")` (server
action). Minimal; no email field (Google-only).

### 2.5 Sign-out + identity in the sidebar

`Sidebar` gains a `user: { name?, email?, image? }` prop (passed from the guarded layout). The
candidate card renders the **real** name/email (replacing M0a's neutral placeholder — no longer
fabricated, it's the session) and includes a **sign-out** control: a `<form action={signOutAction}>`
where `signOutAction` is a `"use server"` action calling `signOut({ redirectTo: "/signin" })`. This
keeps the client `Sidebar` free of `SessionProvider` (server action handles sign-out).

### 2.6 Config/env (web)

`.env.example` gains (placeholders + a "provision in Google Cloud Console" comment):
```
AUTH_SECRET=            # generate: npx auth secret
AUTH_GOOGLE_ID=         # from Google Cloud OAuth client (provisioned later)
AUTH_GOOGLE_SECRET=
```
For local dev/CI without real Google creds: `AUTH_SECRET` is set (dummy is fine) so Auth.js
initializes; the Google round-trip simply won't complete until real creds exist — which does not
block the guard, the `/signin` page, or any test.

---

## 3. API half — DB foundations + first migration

### 3.1 Files

```
apps/api/
  pyproject.toml                     # MODIFY — add deps: sqlalchemy[asyncio], alembic, asyncpg
  specula_api/
    config.py                        # MODIFY — database_url uses the +asyncpg driver form
    db/
      __init__.py                    # CREATE
      base.py                        # CREATE — class Base(DeclarativeBase): pass
      session.py                     # CREATE — async engine + async_sessionmaker
      models.py                      # CREATE — the User model
  alembic.ini                        # CREATE
  alembic/
    env.py                           # CREATE — async env; target_metadata = Base.metadata
    script.py.mako                   # CREATE — Alembic template
    versions/
      <hash>_create_users.py         # CREATE — first migration: citext + users table
  tests/
    test_db.py                       # CREATE — integration: migration applies + User round-trips
    conftest.py                      # CREATE — DB fixtures; skip-if-DB-unreachable
```

`db/` is justified now (≥3 residents). One `User` model → flat `db/models.py` (a `models/` package
arrives when a second model does, in M2 — the folder rule).

### 3.2 The `User` model (`db/models.py`)

Maps to spec §4.1 `users` **minus billing**:
```
class User(Base):
    __tablename__ = "users"
    id:         Mapped[uuid.UUID] = mapped_column(primary_key=True,
                                                  server_default=text("gen_random_uuid()"))
    email:      Mapped[str]       = mapped_column(CITEXT, unique=True)          # citext, not null
    name:       Mapped[str | None]
    google_sub: Mapped[str]       = mapped_column(unique=True)                  # Google account sub
    created_at: Mapped[datetime]  = mapped_column(server_default=func.now())    # timestamptz
```
`gen_random_uuid()` is core in Postgres ≥13 (pg16 ✓). `CITEXT` from
`sqlalchemy.dialects.postgresql`. No `plan`, no `stripe_customer_id`.

### 3.3 Engine/session (`db/session.py`)

- `create_async_engine(settings.database_url)` — lazy; does **not** connect at import (so `main.py`
  still boots without a DB; `/health` stays DB-free).
- `async_session = async_sessionmaker(engine, expire_on_commit=False)`.

### 3.4 First migration

`alembic revision --autogenerate` (target_metadata = `Base.metadata`) or hand-written, producing an
upgrade that:
1. `op.execute("CREATE EXTENSION IF NOT EXISTS citext")`
2. creates `users` (the columns above, with the `email`/`google_sub` unique constraints).
`downgrade` drops `users` (leave the extension). Alembic uses the **async** env template (asyncpg),
reading `settings.database_url`.

### 3.5 Config/env (api)

`config.py` `database_url` default becomes the async form:
`postgresql+asyncpg://specula:specula@localhost:5432/specula`. `.env.example` `DATABASE_URL` updated
to match. Alembic and the engine both read it.

---

## 4. Data flow

- **Login:** browser → `/signin` → `signIn("google")` → Google OAuth → Auth.js callback mints a
  **JWT session cookie** carrying the Google identity (`sub`, email, name). No DB write (bootstrap is
  M2). Subsequent requests to `(app)/*` pass the cookie; the layout guard's `auth()` validates it.
- **Sign-out:** server action `signOut()` clears the cookie → redirect `/signin`.
- **DB:** exercised only by tests and migrations in M0b (no endpoint reads/writes `users` yet — the
  first writer is M2's bootstrap). The engine/session/model exist and are proven by the round-trip test.
- The two halves **do not call each other** in M0b (the web→api service-JWT seam is M2).

---

## 5. Error handling

- **No session** hitting `(app)/*` → `redirect("/signin")` (not an error page). `/signin` is always
  reachable.
- **Missing `AUTH_SECRET`** → Auth.js throws at init; `.env.example` documents it and dev/CI set a
  dummy. **Missing Google creds** → the OAuth redirect fails at Google's end (expected until
  provisioned); the app, guard, and `/signin` still function.
- **DB unreachable** → the engine is lazy (app boots; `/health` unaffected). The DB **test** detects
  unreachability and **skips** (see §6), so offline `just test` stays green.

---

## 6. Testing

**No test requires real Google credentials.**

*Web (Vitest + Playwright):*
- **Vitest:** the `/signin` page renders the "Sign in with Google" button; the sidebar candidate card
  renders the session user's name/email when a `user` prop is supplied, and renders a working sign-out
  control. (The M0a "no fabricated counts" sidebar test still holds — the nav badges remain absent.)
  Mock `next-auth` where a component imports `auth`/`signIn`/`signOut`.
- **Playwright (cred-free):** visiting `/jobs` **unauthenticated** redirects to `/signin`; `/signin`
  shows the Google button. (The authenticated path isn't E2E'd — no creds; covered by Vitest with a
  mocked session.) Existing M0a E2E cases that assumed open access to `(app)` routes are **updated**
  to reflect the guard (they now assert the redirect, or run against a mocked/injected session — the
  plan picks the mechanism; simplest is to assert the redirect for unauth).

*API (pytest integration, skip-if-DB-absent):*
- **Migration applies:** `alembic upgrade head` against the test DB succeeds and creates `users`
  (assert the table exists); `downgrade base` drops it. Proves the harness + migration.
- **Model round-trips:** with the schema present, an async session inserts a `User`
  (email/google_sub/name), commits, and reads it back; assert fields + that a duplicate email/sub
  violates the unique constraint.
- **Skip gate:** a `conftest.py` fixture attempts a connection to `DATABASE_URL`; on failure it
  `pytest.skip("Postgres not reachable")`. So `just test` is green offline; the tests **run** after
  `just up` and **always run in CI** (Postgres service).

*CI:*
- The **api** job gains a **Postgres service container** (`pgvector/pgvector:pg16`, user/pass/db
  `specula`, health-checked), sets `DATABASE_URL` to it, runs `alembic upgrade head`, then `pytest`.
- The **web** job is unchanged in shape but sets a dummy `AUTH_SECRET` (+ dummy Google creds) so the
  build and Playwright run don't fail on missing auth env.

*Gates unchanged:* `just lint`, `just typecheck`, `just test`, `just e2e`, `pre-commit run
--all-files` stay green; ruff/mypy-strict cover the new Python; ESLint/Prettier/tsc cover the new TS.

---

## 7. Acceptance (M0b definition of done)

1. Visiting any `(app)` route **unauthenticated** redirects to `/signin`; `/signin` renders the
   "Sign in with Google" button.
2. `auth.ts` wires the Google provider + JWT session; once real `AUTH_GOOGLE_ID/SECRET` are set, a
   Google sign-in reaches the shell (manually verifiable by the user post-provisioning — not gated by
   automated tests).
3. Signed in, the sidebar candidate card shows the session user's name/email; sign-out returns to
   `/signin`.
4. `apps/api` has async SQLAlchemy + Alembic; `alembic upgrade head` creates the `users` table
   (id/email(citext,unique)/name/google_sub(unique)/created_at — **no billing columns**) on Postgres.
5. The DB integration test **skips** with no Postgres, **passes** with `just up`, and **runs in CI**
   (Postgres service).
6. `just lint && just typecheck && just test && just e2e` green; `pre-commit run --all-files` green;
   CI green (api job with Postgres service + migration; web job with dummy auth env).
7. `.env.example` documents `AUTH_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, and the async
   `DATABASE_URL`. `CLAUDE.md` notes Google-only auth + JWT session + local-docker-DB-for-dev.

---

## 8. Open notes for the plan

- **E2E vs the new guard:** M0a's Playwright cases navigate `(app)` routes directly (previously
  open). Under the guard they'd redirect to `/signin`. The plan must update those cases — the
  low-friction choice is to assert the unauth→`/signin` redirect and keep one authenticated smoke via
  a mocked/injected session cookie if easy; otherwise cover the authenticated shell via Vitest with a
  mocked session. Pick one in the plan; don't leave both.
- **Alembic async vs sync:** use the async env template (asyncpg) so only one driver is needed. If
  autogenerate against async proves fiddly, a hand-written first migration is acceptable (the schema
  is tiny and known).
- **Session TS types:** augment `next-auth` so `session.user.id` is typed (from `token.sub`).
- Everything else is specified above; no TBDs.
