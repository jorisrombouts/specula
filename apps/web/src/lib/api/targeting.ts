import type { Targeting } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export async function getTargeting(): Promise<Targeting> {
  return bffFetch<Targeting>("/targeting");
}
