# M2 Frontend-wiring Lane (last, serial)

The capstone: make the web app genuinely API-backed. Every view fetches real per-user
data from FastAPI through a signed service-JWT; the frontend seed stops being a data
source (it survives only as the DB seeder's fixture). Runs after all 8 backend lanes
(done). Driven inline on branch `m2-frontend-wiring`.

## The service-JWT contract (must match FastAPI `auth.py`)

- alg **HS256**, secret **`SERVICE_JWT_SECRET`** (identical env var on web + api).
- claims: `sub` = `session.user.id` (Google sub), `email`, `name`, `iss="specula-web"`,
  `aud="specula-api"`, `iat`, `exp = iat + 60`. FastAPI requires exp/iat/iss/aud/sub.
- Transport: `Authorization: Bearer <jwt>` on every web→api call. Browser never calls
  FastAPI directly — only the Next server (route handlers / server components) does.

## 1. The real `bffFetch` (`apps/web/src/lib/api/bff.ts`)

Server-side only. Replaces the throwing placeholder. Add `jose` dep. Env:
`SERVICE_JWT_SECRET` + `API_URL` (e.g. `http://localhost:8000`).

```ts
import { SignJWT } from "jose";
import { auth } from "@/auth";

export async function bffFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const session = await auth();
  const sub = session?.user?.id;
  if (!sub) throw new Error("bffFetch: no authenticated session");
  const secret = new TextEncoder().encode(process.env.SERVICE_JWT_SECRET);
  const token = await new SignJWT({ email: session.user.email ?? "", name: session.user.name ?? "" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(sub)
    .setIssuer("specula-web")
    .setAudience("specula-api")
    .setIssuedAt()
    .setExpirationTime("60s")
    .sign(secret);
  const base = process.env.API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}/api/v1${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`bffFetch ${init?.method ?? "GET"} ${path} → ${res.status}`);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
```

## 2. Swap every provider off seed → `bffFetch`

`apps/web/src/lib/api/*.ts`: replace the seed body (and any transitional try/catch seed
fallback) with `bffFetch`. Remove `@/lib/seed/data` imports from providers. The pages
that call them are already/became `async`. Providers + their return types
(`@specula/shared-types`) stay the same. Endpoints: `/jobs`, `/jobs/{id}`, `/lenses`,
`/companies`, `/approvals`, `/insights`, `/skills-gap`, `/candidate`, `/targeting`,
`/tweaks`. **The seed module stays only for the DB seeder** — no frontend runtime path
reads it after this lane.

## 3. Wire the client-mutation BFF routes (`app/api/*/route.ts`)

The route handlers that back client mutations (`companies/[id]`, `jobs/[id]/state`,
`approvals/[id]/decision`, `tweaks`) forward to FastAPI via `bffFetch` (drop the
transitional 501/echo TODOs). They run server-side, so `auth()` works.

## 4. Candidate + tweaks

- Candidate: wire the form save (`PUT /candidate`) — the one lane that deferred its FE
  entirely. Compose `Candidate.name`/`initials` from the session user (no
  `candidate_profiles.name` column).
- Tweaks: `GET /api/tweaks` now returns the user's **stored** prefs (real backend), so
  the mount reconcile no longer reverts local prefs to defaults — resolves the
  transitional UX flagged on the board.

## 5. Test harness runs the real stack (this is what keeps CI honest)

Because providers now require FastAPI, the Playwright `authed` (E2E) and `visual`
projects must run FastAPI + a seeded Postgres with a matching `SERVICE_JWT_SECRET` +
`API_URL`. Update `playwright.config.ts` + `playwright.visual.config.ts` webServers to
also start `uvicorn` against a seeded DB; wire the web CI job with a Postgres service +
uv + the role/extension/migrate/seed steps (mirror the api job). The minted-cookie
session already gives `auth()` a session; bffFetch then mints the service JWT to the
local API. Baselines shouldn't shift (same seeded data, same layout) — regenerate only
if a genuine visual change appears.

## Definition of done

- Every view renders real API data; every mutation persists through FastAPI.
- `pnpm typecheck / lint / test` green; `just e2e` + visual green against the real
  stack; `just test` (api) green.
- Manual smoke: sign-in bypass → drive each view, mutate (set a job status, edit
  candidate, toggle tracking, approve a company, change a tweak), reload, confirm
  persistence + cross-tenant isolation.
- No frontend runtime path imports `@/lib/seed/data`.
