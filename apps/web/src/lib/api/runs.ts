import type { Run, RateLimitError } from "@specula/shared-types";
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
  if (res.ok) return res.json() as Promise<Run>;
  // Surface WHY it failed. A rate-limit carries the seconds to wait (RateLimitError shape);
  // anything else reports its status so a break is at least legible instead of silent.
  if (res.status === 429) {
    const body = (await res.json().catch(() => null)) as RateLimitError | null;
    const secs = body?.retryAfterS;
    throw new Error(
      secs
        ? `Rate-limited — try again in ${secs}s.`
        : "Rate-limited — try again shortly.",
    );
  }
  throw new Error(`Sync failed (${res.status}).`);
}
