import type { Job, JobSort } from "@specula/shared-types";
import { filterByLens, scoreForLens, sortJobs } from "@/lib/seed/logic";

// The Jobs filter→score→sort orchestration used by the client JobsView to
// re-derive its own per-lens ranking over the server-scored pool for the
// FLIP-animated list. M2: the pool comes from the API (already scored for the
// "all" lens); `/api/jobs` (getJobs) now forwards FastAPI's own scored+sorted
// response instead of calling this, so this is no longer literally shared
// with the route — see the M2 frontend-wiring report for the known gap this
// leaves (lens ids here are seed-only sentinels, not real per-user lens ids).
export function scoredList(pool: Job[], lens: string, sort: JobSort): Job[] {
  const scored = filterByLens(pool, lens).map((job) => ({
    ...job,
    ...scoreForLens(job, lens),
  }));
  return sortJobs(scored, sort);
}
