import type { LensSummary } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";

// M2: BFF → FastAPI `GET /api/v1/lenses` (returns LensSummary[] with server-derived
// count/isNew). Blocked on the shared `bffFetch` + service-JWT minter built by the
// Frontend-wiring lane; until it lands, keep serving seed-derived summaries so the
// Jobs/Profiles views still render. The Profiles toggle → `PATCH /lenses/{id}` wiring
// (profiles-view.tsx) depends on the same client mutation path.
export function getLenses(): LensSummary[] {
  return deriveLensSummaries(lenses, jobs);
}
