import type { Candidate } from "@specula/shared-types";
import { candidate } from "@/lib/seed/data";

export function getCandidate(): Candidate {
  return candidate;
}
