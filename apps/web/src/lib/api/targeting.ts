import type { Targeting } from "@specula/shared-types";
import { targeting } from "@/lib/seed/data";

// M2: BFF → FastAPI.
export function getTargeting(): Targeting {
  return targeting;
}
