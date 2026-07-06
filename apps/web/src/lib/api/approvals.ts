import type { Approval } from "@specula/shared-types";
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
  if (!res.ok) throw new Error(`Approval decision failed (${res.status})`);
}
