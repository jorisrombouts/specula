import type { LensSummary } from "@specula/shared-types";
import { jobs, lenses } from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";

export function getLenses(): LensSummary[] {
  return deriveLensSummaries(lenses, jobs);
}
