import type {
  Job,
  JobSort,
  JobStatus,
  JobsResponse,
} from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// The full deduped pool, already scored (server-side) against the "all" lens,
// sorted by match. The client (JobsView) re-derives its own per-lens
// filter/score/sort over this pool for the FLIP-animated list — see
// `lib/jobs-scoring.ts`.
export async function getJobsPool(): Promise<Job[]> {
  const res = await bffFetch<JobsResponse>("/jobs?sort=match");
  return res.jobs;
}

export async function getJob(id: string): Promise<Job | null> {
  try {
    return await bffFetch<Job>(`/jobs/${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}

// The lens-filtered, re-scored, sorted list + derived lens summaries — already
// computed server-side. Do not re-derive with scoredList/deriveLensSummaries
// here; that's the client's job (see lib/jobs-scoring.ts).
export async function getJobs(
  lens: string,
  sort: JobSort,
): Promise<JobsResponse> {
  return bffFetch<JobsResponse>(
    `/jobs?lens=${encodeURIComponent(lens)}&sort=${sort}`,
  );
}

// The drawer's posting-state mutation (status / note / feedback / dismiss reason).
export type JobStatePatch = {
  status?: JobStatus | null;
  note?: string;
  dismissReason?: string;
  feedback?: "positive" | "negative" | null;
};

// Client-side: persists through the BFF route → FastAPI PATCH /jobs/{id}/state.
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
