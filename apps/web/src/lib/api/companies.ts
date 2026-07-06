import type { Company } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// The GET /companies API also returns `id` + `tracking` (needed to wire the row
// toggle). The shared Company contract is display-only, so extend it locally
// rather than mutating @specula/shared-types.
export type CompanyRow = Company & { id?: string; tracking?: boolean };

export async function getCompanies(): Promise<CompanyRow[]> {
  return bffFetch<CompanyRow[]>("/companies");
}

// Client-side: persist a per-row tracking toggle through the BFF route.
export async function setCompanyTracking(
  id: string,
  tracking: boolean,
): Promise<void> {
  const res = await fetch(`/api/companies/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tracking }),
  });
  if (!res.ok) throw new Error(`Failed to update tracking (${res.status})`);
}
