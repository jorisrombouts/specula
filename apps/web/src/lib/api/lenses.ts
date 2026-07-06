import type { LensSummary } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export async function getLenses(): Promise<LensSummary[]> {
  return bffFetch<LensSummary[]>("/lenses");
}
