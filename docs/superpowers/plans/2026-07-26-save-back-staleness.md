# Fix save→back staleness (RSC cache) — implementation plan

**Goal:** After a client mutation of server-rendered data, call `router.refresh()` so a
save → navigate-away → browser-Back round-trip shows the saved state, not the stale cached
pre-save state. Candidate & Targeting are already fixed (uncommitted, by the user); extend the
same one-line pattern to the remaining broken pages and commit the whole fix together.

**Root cause (confirmed):** Next App Router caches a route's RSC payload and reuses it on
back/forward. A client mutation persists to the DB but doesn't invalidate that cache, so Back
re-renders the pre-mutation server data. Confirmed live: toggling a lens off on Search profiles,
navigating away, and hitting Back shows the lens back **on**. `router.refresh()` drops the cache.

**Constraints:** tsc + eslint + prettier + vitest green. Mirror the exact pattern the user used
in `candidate-view.tsx`/`targeting-view.tsx` (call `router.refresh()` in the success path, after
the persisted `await`). **Stage only the files this fix touches** (the user's candidate/targeting
edits are part of this fix and get committed together; nothing else in the working tree).

## Affected components (mutate server data, no `router.refresh()`)

| Component | Mutation(s) | Fix |
|---|---|---|
| `profiles/profiles-view.tsx` | `save` (create/update lens), `remove` (delete), `toggle` (active) | add `useRouter`; `router.refresh()` after each success |
| `companies/companies-view.tsx` | `remove` → `optOutCompany` | add `useRouter`; `router.refresh()` after opt-out resolves |
| `jobs/job-drawer.tsx` | `patch` → `onPatchState` (status / feedback / note) | add `useRouter`; `router.refresh()` when the PATCH resolves |
| _already fixed_ | `candidate-view`, `targeting-view` | commit the user's existing edits with this fix |

## Tasks

- [ ] **T1 — profiles-view.** Add `import { useRouter } from "next/navigation"` + `const router = useRouter()`. In `save`, `remove`, and `toggle`, call `router.refresh()` after the `await create/update/deleteLens(...)` succeeds. `profiles-view.test.tsx`: it already renders through mutations — add `vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }))` if not present. Run its tests.

- [ ] **T2 — companies-view.** Add `useRouter`; in `remove`, call `router.refresh()` after `optOutCompany(c.id)` resolves (inside the existing `.then`/await success path, before the catch rollback). Re-add the `next/navigation` mock to `companies-view.test.tsx` (removed when the discovery button left this file). Keep the optimistic drop; refresh only reconciles the server list so Back isn't stale.

- [ ] **T3 — job-drawer.** Add `useRouter`; in `patch`, on the promise's success settle `router.refresh()` (two-arg `.then(onOk, onErr)` — refresh on ok, revert on err). Add the `next/navigation` mock to `job-drawer.test.tsx`.

- [ ] **T4 — verify + commit.** `pnpm exec tsc --noEmit`, `pnpm exec vitest run`, `pnpm lint` green. Commit `profiles-view.tsx`+test, `companies-view.tsx`+test, `job-drawer.tsx`+test, **and** the user's `candidate-view.tsx`/`.test.tsx` + `targeting-view.tsx`/`.test.tsx`, as `fix(rsc): refresh after config/list mutations so Back isn't stale`.

## Verification (headless, acceptance)

For each of profiles (toggle a lens), companies (remove a company), jobs (open a job → change
status), candidate (edit headline), targeting (edit preferences): mutate → click the Jobs nav →
browser Back → assert the mutated value **persisted** (fresh, not reverted). Restore any mutated
demo data after. Then merge to `main` + push.
