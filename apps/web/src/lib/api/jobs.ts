import type { Job, JobSort, JobsResponse } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import {
  filterByLens,
  scoreForLens,
  deriveLensSummaries,
  sortJobs,
} from "@/lib/seed/logic";

// The full deduped pool, base-scored (lens-independent). M2: BFF → FastAPI.
export function getJobsPool(): Job[] {
  return jobs.slice();
}

export function getJob(id: string): Job | null {
  return jobs.find((j) => j.id === id) ?? null;
}

// The lens-filtered, re-scored, sorted list + derived lens summaries.
export function getJobs(lens: string, sort: JobSort): JobsResponse {
  const scored = filterByLens(jobs, lens).map((job) => {
    const s = scoreForLens(job, lens);
    return { ...job, match: s.match, factors: s.factors, redFlag: s.redFlag };
  });
  return {
    jobs: sortJobs(scored, sort),
    lenses: deriveLensSummaries(lenses, jobs),
    sort,
  };
}
