import type { SkillsGap } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export async function getSkillsGap(): Promise<SkillsGap[]> {
  return bffFetch<SkillsGap[]>("/skills-gap");
}
