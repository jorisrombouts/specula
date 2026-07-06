import type { Insights } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export async function getInsights(
  period: "4w" | "8w" | "q" = "q",
): Promise<Insights> {
  return bffFetch<Insights>(`/insights?period=${period}`);
}
