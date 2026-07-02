import type { Candidate } from "@specula/shared-types";

export function candidateHas(candidate: Candidate, skill: string): boolean {
  const cs = candidate.skills.map((s) => s.toLowerCase());
  const t = skill.toLowerCase();
  return cs.some(
    (c) => c === t || c.includes(t) || t.includes(c.split(" ")[0]),
  );
}

export function splitSkills(
  candidate: Candidate,
  required: string[],
): { have: string[]; miss: string[] } {
  return {
    have: required.filter((s) => candidateHas(candidate, s)),
    miss: required.filter((s) => !candidateHas(candidate, s)),
  };
}
