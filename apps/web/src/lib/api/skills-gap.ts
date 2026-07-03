import type { SkillsGap } from "@specula/shared-types";
import { skillsGap } from "@/lib/seed/data";

export function getSkillsGap(): SkillsGap[] {
  return skillsGap.slice();
}
