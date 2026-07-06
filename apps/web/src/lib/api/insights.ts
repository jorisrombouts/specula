import type { Insights } from "@specula/shared-types";
import { insights } from "@/lib/seed/data";

// M2: BFF → FastAPI `GET /api/v1/insights?period={4w|8w|q}`.
// Backend is live and tenant-scoped; final swap is:
//   export async function getInsights(period: "4w" | "8w" | "q" = "8w"): Promise<Insights> {
//     return bffFetch<Insights>(`/insights?period=${period}`);
//   }
// Blocked on the shared `bffFetch` (service-JWT minter), owned by the Frontend-wiring
// lane. Wire the inert period <select> in insights-view.tsx to pass `period` through.
export function getInsights(): Insights {
  return insights;
}
