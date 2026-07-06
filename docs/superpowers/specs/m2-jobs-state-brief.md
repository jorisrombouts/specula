# M2 Fan-out Lane: jobs + state (the meatiest lane)

**Read `m2-fanout-playbook.md` first.** This lane is the read-model over the seeded
pool + the posting-state mutation. It's the largest — budget accordingly.

**Endpoints:** `GET /jobs?lens={id}&sort={match|deadline|new}`, `GET /jobs/{id}`,
`PATCH /jobs/{id}/state`.
**Models:** `Posting` + `Score` + `PostingState` + `Company` (join).
**Contract:** match `Job`, `JobsResponse` in `packages/shared-types/src/index.ts`.
**FE provider:** `apps/web/src/lib/api/jobs.ts` (`getJobsPool`/`getJob`/`getJobs`),
consumed by `jobs-view.tsx` + `job-drawer.tsx` — wire the drawer's status/note/feedback
controls (currently inert/readOnly) to `PATCH /jobs/{id}/state`.

**Specifics:**
- **`GET /jobs`** returns the deduped, scored pool for a lens: join
  `postings ⋈ companies ⋈ scores ⋈ posting_state`, filter by the lens via
  `services/lens_filter.py` `lens_where(lens)`, and **derive per-lens** `factor_loc` +
  overall `match` + the lens summaries' `count`/`isNew` at read time (NEVER stored). Port
  the scoring/derive math from `apps/web/src/lib/seed/logic.ts` (`scoreForLens`,
  `deriveLensSummaries`) and `apps/web/src/lib/jobs-scoring.ts`. Salary never affects
  sort/filter.
- **`lens_where` is shared with the lenses lane** — build it here if it doesn't exist
  (it's the accepted inter-lane dependency); otherwise reuse. Coordinate: whichever lane
  lands first owns the file, the other rebases.
- **`GET /jobs/{id}`** returns the full insight record + score + state for the drawer.
- **`PATCH /jobs/{id}/state`** upserts `posting_state` (status/note/feedback/
  dismiss_reason). Set its `user_id` from the posting's owner (see playbook rule 6).
  Returns the updated resource (for optimistic UI reconcile).

**Tests:** lens filter correctness (foreign_hq/modes/default), derived-not-stored counts,
sort variants, state PATCH persists + round-trips, cross-tenant isolation.
