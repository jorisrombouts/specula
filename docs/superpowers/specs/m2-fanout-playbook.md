# M2 Fan-out Lane Playbook (read this first)

Shared instructions for every M2 fan-out CRUD lane. Your per-lane brief
(`m2-<lane>-brief.md`) names the endpoints, model(s), and frontend provider; this
playbook is the how. You are in a git worktree on branch `m2-<lane>` with your own
database (`specula_wt_<lane>`, already migrated + seeded). Postgres is on host port
**55432**; you connect as the non-superuser `specula_app` role.

## The foundation you build on (already on `main`)

- **Models:** `specula_api/db/models/` — every §4 table. Import from
  `specula_api.db.models`.
- **The copy-me template — clone this exactly:** `specula_api/schemas/targeting.py`,
  `specula_api/services/targeting.py`, `specula_api/routers/targeting.py`, and
  `tests/test_targeting_api.py`. Your lane is the same shape with your model/fields.
- **Deps:** `from specula_api.deps import get_current_user_id, get_session`. Every
  route takes `user_id: UUID = Depends(get_current_user_id)` and
  `session: AsyncSession = Depends(get_session)`.
- **Router wiring:** add `api_router.include_router(<lane>.router)` in
  `specula_api/routers/__init__.py`.
- **Auth in tests:** `from specula_api.auth import mint`; send
  `Authorization: Bearer {mint(sub=<random>, email=...)}`. Monkeypatch
  `settings.service_jwt_secret` per-run like `tests/test_auth.py` does.

## Hard rules (a reviewer will reject violations)

1. **Never expose or accept `user_id`** in a schema. It comes from the JWT.
2. **Services `flush()`, never `commit()`/`rollback()`** — `get_session` owns the
   transaction (a mid-request commit drops the `app.user_id` GUC → RLS breaks).
3. **Scope every query by `user_id`** in the service (belt-and-suspenders alongside
   RLS), exactly as `services/targeting.py` does.
4. **camelCase at the API boundary** — reuse the `CamelModel` base pattern
   (`alias_generator=to_camel, populate_by_name=True`) so responses match
   `packages/shared-types/src/index.ts`. Check your resource's TS interface there and
   match its field names.
5. **Product invariants:** counts are DERIVED server-side (never stored/returned from a
   column); salary never ranks/filters; low-confidence postings
   (`extraction_confidence` low) are excluded from Insights aggregates.
6. For rows that carry both `posting_id` and `user_id` (scores/posting_state), set
   `user_id` from the owning posting — never from client input.

## TDD + verification

Write the failing test first, then implement. Every lane ships:
- CRUD happy-path tests through real HTTP (`httpx.AsyncClient(transport=ASGITransport(
  app=create_app()))`), `requires_db`-guarded (copy the guard from `tests/test_db.py`).
- **A cross-tenant test**: a second user (different `sub`) never sees the first's rows.
- Green: `cd apps/api && uv run pytest -q && uv run mypy . && uv run ruff check &&
  uv run ruff format --check`.

## Frontend wiring (your lane's provider)

Swap your provider in `apps/web/src/lib/api/<x>.ts` from returning seed data to an
`await bffFetch(...)` call, and wire the inert UI control(s) your resource owns (the
brief names them). The shared `bffFetch` + service-JWT minter is built by the
**Frontend-wiring lane** (runs last) — if it doesn't exist yet, stub your provider
change behind it and note the dependency in your report; don't build the shared minter
yourself. Keep the `@specula/shared-types` types unchanged (they're the contract).

## Done = commit on your branch

When green, commit on `m2-<lane>` with a clear message. Do NOT merge to `main` — the
human integrates. Report: what you built, test results, and any inter-lane dependency
you hit.
