import type { Approval, RateLimitError } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export type ApprovalDecision = "approve" | "reject" | "snooze";

export async function getApprovals(): Promise<Approval[]> {
  return bffFetch<Approval[]>("/approvals");
}

// Persist a queue decision via the BFF route (which proxies to FastAPI
// `POST /approvals/{id}/decision`). Client-side; throws on a non-2xx response.
export async function postApprovalDecision(
  id: string,
  decision: ApprovalDecision,
): Promise<void> {
  const res = await fetch(`/api/approvals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (res.ok) return;
  // Say WHY it failed. A rate-limited approve carries the seconds to wait; anything else
  // reports its status so the queue doesn't just silently reject the card.
  if (res.status === 429) {
    const body = (await res.json().catch(() => null)) as RateLimitError | null;
    const secs = body?.retryAfterS;
    throw new Error(
      secs
        ? `Rate-limited — try again in ${secs}s.`
        : "Rate-limited — try again shortly.",
    );
  }
  throw new Error(`Couldn't ${decision} (${res.status}).`);
}
