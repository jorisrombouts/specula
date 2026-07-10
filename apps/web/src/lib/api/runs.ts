import type { Run } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// Server-side: the most recent run for the caller, or null if none has ever run.
export async function getLatestRun(): Promise<Run | null> {
  return bffFetch<Run | null>("/runs/latest");
}

// Server-side: a single run by id.
export async function getRun(id: string): Promise<Run> {
  return bffFetch<Run>(`/runs/${encodeURIComponent(id)}`);
}

// Client-side: triggers a new pipeline run via the BFF route (which proxies to
// FastAPI `POST /runs`). Returns the created run (status "queued").
export async function triggerRun(): Promise<Run> {
  const res = await fetch("/api/runs", { method: "POST" });
  if (!res.ok) throw new Error(`Trigger run failed (${res.status})`);
  return res.json() as Promise<Run>;
}
