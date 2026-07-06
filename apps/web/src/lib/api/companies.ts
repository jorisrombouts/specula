import type { Company } from "@specula/shared-types";
import { companies } from "@/lib/seed/data";
import { bffFetch } from "@/lib/api/bff";

// The GET /companies API also returns `id` + `tracking` (needed to wire the row
// toggle). The shared Company contract is display-only, so extend it locally
// rather than mutating @specula/shared-types.
export type CompanyRow = Company & { id?: string; tracking?: boolean };

// M2: BFF → FastAPI. Transitional seed fallback until the Frontend-wiring lane
// lands the real service-JWT-minting bffFetch — remove the fallback then.
export async function getCompanies(): Promise<CompanyRow[]> {
  try {
    return await bffFetch<CompanyRow[]>("/companies");
  } catch {
    return companies.slice();
  }
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
