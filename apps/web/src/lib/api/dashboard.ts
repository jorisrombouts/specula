import type { DashboardSummary } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export async function getDashboard(): Promise<DashboardSummary> {
  return bffFetch<DashboardSummary>("/dashboard");
}
