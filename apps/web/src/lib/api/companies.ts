import type { Company } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// The GET /companies API also returns `id` (needed to target a row's opt-out).
// The shared Company contract is display-only, so extend it locally rather than
// mutating @specula/shared-types.
export type CompanyRow = Company & { id?: string; tracking?: boolean };

export async function getCompanies(): Promise<CompanyRow[]> {
  return bffFetch<CompanyRow[]>("/companies");
}

// Client-side: "remove" a company via the BFF opt-out route — excludes it from
// future discovery/ingest and drops it from the registry. Throws on a non-2xx.
export async function optOutCompany(id: string): Promise<void> {
  const res = await fetch(`/api/companies/${id}/opt-out`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to remove company (${res.status})`);
}
