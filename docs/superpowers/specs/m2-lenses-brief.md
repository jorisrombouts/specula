# M2 Fan-out Lane: lenses

**Read `m2-fanout-playbook.md` first.** Then build the lenses CRUD vertical.

**Endpoints:** `GET /lenses`, `POST /lenses`, `PATCH /lenses/{id}`, `DELETE /lenses/{id}`.
**Model:** `Lens` (`specula_api/db/models/lens.py`) — 1:N per user.
**Contract:** match `Lens`/`LensSummary` in `packages/shared-types/src/index.ts`.
**FE provider:** `apps/web/src/lib/api/lenses.ts` (`getLenses`), consumed by
`profiles-view.tsx` (the active toggle) — wire `PATCH /lenses/{id}` for the toggle.

**Specifics:**
- `GET /lenses` returns each lens **with derived counts** (`count`, `isNew`) — these are
  computed server-side by applying the lens filter to the seeded `postings`, NEVER stored
  as columns. You'll need `services/lens_filter.py` `lens_where(lens)` → SQLAlchemy
  predicates over `postings ⋈ companies` (foreign_hq = `postings.hq_country <>
  postings.country`; modes → `work_mode IN (...)`; scope → location; default `All` → no
  filter). **This util is shared with the jobs-state lane** — if it doesn't exist yet,
  build it here (port semantics from `apps/web/src/lib/seed/logic.ts` `filterByLens` +
  `deriveLensSummaries`); if jobs-state already built it, reuse and rebase.
- Protect the default lens: `is_default=True` ("All") cannot be deleted; enforce exactly
  one default per user.
- `POST` creates; `PATCH` partial-updates (name/scope/modes/origin_rule/focus/active);
  `DELETE` removes a non-default lens.

**Tests:** CRUD happy-path + counts-are-derived (create a lens, assert its count matches a
direct filter query) + cannot-delete-default + cross-tenant isolation.
