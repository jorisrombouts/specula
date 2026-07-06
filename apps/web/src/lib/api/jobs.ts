import type {
  Job,
  JobSort,
  JobStatus,
  JobsResponse,
} from "@specula/shared-types";
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

// The drawer's posting-state mutation (status / note / feedback / dismiss reason).
export type JobStatePatch = {
  status?: JobStatus | null;
  note?: string;
  dismissReason?: string;
  feedback?: "positive" | "negative" | null;
};

// M2: goes through the BFF route → FastAPI PATCH /jobs/{id}/state. The route currently
// echoes the patch for optimistic reconcile until the Frontend-wiring lane lands the
// shared service-JWT `bffFetch`.
export async function patchJobState(
  id: string,
  patch: JobStatePatch,
): Promise<JobStatePatch> {
  const res = await fetch(`/api/jobs/${id}/state`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Failed to update job state (${res.status})`);
  return res.json() as Promise<JobStatePatch>;
}
