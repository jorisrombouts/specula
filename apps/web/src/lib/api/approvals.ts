import type { Approval } from "@specula/shared-types";
import { approvals } from "@/lib/seed/data";

// M2: BFF → FastAPI.
export function getApprovals(): Approval[] {
  return approvals.slice();
}
