import type { Job, JobSort, JobsResponse } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";
import { scoredList } from "@/lib/jobs-scoring";

// The full deduped pool, base-scored (lens-independent). M2: BFF → FastAPI.
export function getJobsPool(): Job[] {
  return jobs.slice();
}

export function getJob(id: string): Job | null {
  return jobs.find((j) => j.id === id) ?? null;
}

// The lens-filtered, re-scored, sorted list + derived lens summaries.
export function getJobs(lens: string, sort: JobSort): JobsResponse {
  return {
    jobs: scoredList(jobs, lens, sort),
    lenses: deriveLensSummaries(lenses, jobs),
    sort,
  };
}
