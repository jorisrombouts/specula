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

// Turn a failed trigger Response into a specific Error. A rate-limit (429) carries the seconds
// to wait (RateLimitError shape); anything else reports its status so a break stays legible
// instead of silent. `failed` is the non-429 lead-in, e.g. "Sync failed".
async function triggerError(res: Response, failed: string): Promise<Error> {
  if (res.status === 429) {
    const body = (await res.json().catch(() => null)) as RateLimitError | null;
    const secs = body?.retryAfterS;
    return new Error(
      secs
        ? `Rate-limited — try again in ${secs}s.`
        : "Rate-limited — try again shortly.",
    );
  }
  return new Error(`${failed} (${res.status}).`);
}

// Client-side: triggers a new pipeline run via the BFF route (which proxies to
// FastAPI `POST /runs`). Returns the created run (status "queued").
export async function triggerRun(): Promise<Run> {
  const res = await fetch("/api/runs", { method: "POST" });
  if (res.ok) return res.json() as Promise<Run>;
  throw await triggerError(res, "Sync failed");
}

// Client-side: re-score all existing jobs against the CURRENT profile (POST /runs/rescore).
// Returns the created rescore run (status "queued"); poll fetchRun to follow it to completion.
export async function triggerRescore(): Promise<Run> {
  const res = await fetch("/api/runs/rescore", { method: "POST" });
  if (res.ok) return res.json() as Promise<Run>;
  throw await triggerError(res, "Re-score failed");
}

// Client-side: fetch one run by id — used to poll a rescore run to its terminal status.
export async function fetchRun(id: string): Promise<Run> {
  const res = await fetch(`/api/runs/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Couldn't load run (${res.status}).`);
  return res.json() as Promise<Run>;
}
