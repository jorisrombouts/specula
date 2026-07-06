import type { Candidate } from "@specula/shared-types";
import { candidate } from "@/lib/seed/data";

// M2: BFF → FastAPI (GET/PUT /api/v1/candidate). Awaiting shared `bffFetch` +
// service-JWT minter from the Frontend-wiring lane before swapping off seed data.
export function getCandidate(): Candidate {
  return candidate;
}
