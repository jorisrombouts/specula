# M2 Fan-out Lane: candidate

**Read `m2-fanout-playbook.md` first.** This is the closest clone of the targeting
template (also a 1:1 GET/PUT resource) — start by copying targeting's four files.

**Endpoints:** `GET /candidate`, `PUT /candidate`.
**Model:** `CandidateProfile` (`db/models/candidate_profile.py`) — 1:1, `user_id` PK.
**Contract:** match `Candidate` in `packages/shared-types/src/index.ts`
(name, skills[], projects[], experience[], plus headline/location/work_mode/visa/years/
education/languages).
**FE provider:** `apps/web/src/lib/api/candidate.ts` (`getCandidate`), consumed by
`candidate-view.tsx` — wire the skills `TagEditor` + field edits to `PUT /candidate`.

**Specifics:**
- Exactly the targeting shape: `TargetingIn`→`CandidateIn`, `upsert_candidate` keyed on
  `user_id` PK, GET returns empty defaults when the row is missing.
- `projects`/`experience` are JSONB arrays of objects — type them as
  `list[dict[str, str]]` in the schema.
- **Leave `skills_vec` NULL** — re-embedding on write is a later (M4) lane; do not add
  embedding logic. Just persist the explicit `skills` text[].
- No salary anywhere.

**Tests:** GET empty-defaults, PUT persists/echoes (camelCase), cross-tenant isolation.
