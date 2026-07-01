import type {
  Job,
  Lens,
  LensSummary,
  JobSort,
  Factors,
} from "@specula/shared-types";
import { lenses } from "@/lib/seed/data";

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));

export function filterByLens(jobs: Job[], lensId: string): Job[] {
  const lens = lenses.find((l) => l.id === lensId);
  if (!lens || lensId === "all") return jobs.slice();
  return jobs.filter((j) => {
    if (lens.modes && !lens.modes.includes(j.mode)) return false;
    if (lensId === "remote") return j.mode === "Remote";
    if (lensId === "foreign") return j.hq !== j.country;
    if (lensId === "spain") return j.country === "ES";
    if (lensId === "berlin") return j.city === "Berlin";
    return true;
  });
}

export function locForLens(job: Job, lensId: string): number {
  if (lensId === "all") return job.factors.loc;
  const remote = job.mode === "Remote",
    hybrid = job.mode === "Hybrid";
  const euTz = ["NL", "DE", "FR", "ES", "IE", "PT", "BE", "AT"].includes(
    job.country,
  );
  if (lensId === "remote") {
    let f = remote ? 92 : hybrid ? 58 : 32;
    f += euTz ? 6 : job.country === "GB" ? 0 : -6;
    return clamp(f);
  }
  if (lensId === "foreign") {
    let f = job.hq !== job.country ? 88 : 48;
    f += remote ? 6 : hybrid ? 0 : -6;
    return clamp(f);
  }
  if (lensId === "spain") {
    let f = job.country === "ES" ? 88 : 42;
    f += job.city === "Barcelona" || job.city === "Madrid" ? 6 : 0;
    return clamp(f);
  }
  if (lensId === "berlin") {
    let f = job.city === "Berlin" ? 92 : job.country === "DE" ? 68 : 44;
    f += hybrid || job.mode === "On-site" ? 4 : remote ? -8 : 0;
    return clamp(f);
  }
  return job.factors.loc;
}

export function scoreForLens(
  job: Job,
  lensId: string,
): { match: number; factors: Factors; redFlag?: string } {
  if (lensId === "all")
    return { match: job.match, factors: job.factors, redFlag: job.redFlag };
  const role = job.factors.role,
    skill = job.factors.skill;
  const loc = locForLens(job, lensId);
  let match = clamp(0.4 * role + 0.4 * skill + 0.2 * loc);
  let redFlag = job.redFlag;
  if (skill < 45) {
    redFlag = redFlag || "Low required-skill overlap";
    match = Math.min(match, 72);
  }
  return { match, factors: { role, skill, loc }, redFlag };
}

export function deriveLensSummaries(
  lenses: Lens[],
  jobs: Job[],
): LensSummary[] {
  return lenses.map((lens) => {
    const pool = filterByLens(jobs, lens.id);
    return {
      ...lens,
      count: pool.length,
      isNew: pool.filter((j) => j.isNew).length,
    };
  });
}

export function sortJobs(jobs: Job[], sort: JobSort): Job[] {
  const out = jobs.slice();
  if (sort === "match") out.sort((a, b) => b.match - a.match);
  else if (sort === "deadline")
    out.sort((a, b) => a.deadlineDays - b.deadlineDays);
  else if (sort === "new")
    out.sort((a, b) => Number(b.isNew) - Number(a.isNew));
  return out;
}
