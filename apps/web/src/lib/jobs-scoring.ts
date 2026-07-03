import type { Job, JobSort } from "@specula/shared-types";
import { filterByLens, scoreForLens, sortJobs } from "@/lib/seed/logic";

// Single source of the Jobs filter→score→sort orchestration. Used by both the
// /api/jobs route (getJobs) and the client JobsView, so the HTTP contract and
// the FLIP-animated client list can never drift. M2: the pool comes from the API.
export function scoredList(pool: Job[], lens: string, sort: JobSort): Job[] {
  const scored = filterByLens(pool, lens).map((job) => ({
    ...job,
    ...scoreForLens(job, lens),
  }));
  return sortJobs(scored, sort);
}
