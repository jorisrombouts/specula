import type { SkillsGap } from "@specula/shared-types";
import { skillsGap } from "@/lib/seed/data";

// M2: BFF → FastAPI `GET /api/v1/skills-gap`.
// Backend is live and tenant-scoped; final swap is:
//   export async function getSkillsGap(): Promise<SkillsGap[]> {
//     return bffFetch<SkillsGap[]>("/skills-gap");
//   }
// Blocked on the shared `bffFetch` (service-JWT minter), owned by the Frontend-wiring lane.
export function getSkillsGap(): SkillsGap[] {
  return skillsGap.slice();
}
