// Test-only fixtures + a `bffFetch` stand-in, so unit/component tests can
// `vi.mock("@/lib/api/bff")` and exercise the now-async, API-backed providers
// (lib/api/*.ts) without a real FastAPI + service-JWT session. Not imported by
// any page/route — the seed module it draws from stays a seeder-only fixture
// at runtime (see docs/superpowers/specs/m2-frontend-wiring-brief.md).
import type {
  Approval,
  Insights,
  JobsResponse,
  JobSort,
  LensSummary,
  SkillsGap,
  Targeting,
} from "@specula/shared-types";
import {
  approvals as seedApprovals,
  candidate as seedCandidate,
  companies as seedCompanies,
  insights as seedInsights,
  jobs as seedJobs,
  lenses as seedLenses,
  skillsGap as seedSkillsGap,
  targeting as seedTargeting,
} from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";
import { scoredList } from "@/lib/jobs-scoring";
import { TWEAK_DEFAULTS, type Tweaks } from "@/lib/tweaks-init";
import type { CompanyRow } from "@/lib/api/companies";

// Mirrors `CandidateApiOut` in lib/api/candidate.ts (FastAPI's `CandidateOut`,
// camelCased): `headline` stands in for the seed's `title`; there's no
// name/initials field.
export const candidateApiFixture = {
  headline: seedCandidate.title,
  location: seedCandidate.location,
  workMode: seedCandidate.workMode,
  visa: seedCandidate.visa,
  years: seedCandidate.years,
  education: seedCandidate.education,
  languages: seedCandidate.languages,
  skills: seedCandidate.skills,
  projects: seedCandidate.projects,
  experience: seedCandidate.experience,
};

export const targetingApiFixture: Targeting = seedTargeting;
export const approvalsApiFixture: Approval[] = seedApprovals;
export const insightsApiFixture: Insights = seedInsights;
export const skillsGapApiFixture: SkillsGap[] = seedSkillsGap;
export const lensesApiFixture: LensSummary[] = deriveLensSummaries(
  seedLenses,
  seedJobs,
);
export const companiesApiFixture: CompanyRow[] = seedCompanies.map((c, i) => ({
  ...c,
  id: `co-${i + 1}`,
  tracking: true,
}));
export const tweaksApiFixture: Tweaks = TWEAK_DEFAULTS;

function jobsResponseFixture(lens: string, sort: JobSort): JobsResponse {
  return {
    jobs: scoredList(seedJobs, lens, sort),
    lenses: lensesApiFixture,
    sort,
  };
}

function parseJobsQuery(path: string): { lens: string; sort: JobSort } {
  const params = new URLSearchParams(path.split("?")[1] ?? "");
  const sortParam = params.get("sort");
  const sort: JobSort =
    sortParam === "deadline" || sortParam === "new" ? sortParam : "match";
  return { lens: params.get("lens") ?? "all", sort };
}

// `init`-aware: a PUT/PATCH/POST echoes its (parsed) body merged over the
// matching fixture, mirroring FastAPI's "persist and return the row" routes
// closely enough for the mutation-adjacent tests (e.g. tweaks PUT, job-state
// PATCH) to stay meaningful.
export async function mockBffFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const body = init?.body
    ? (JSON.parse(init.body as string) as Record<string, unknown>)
    : undefined;

  if (path === "/candidate") {
    return { ...candidateApiFixture, ...body } as T;
  }
  if (path === "/targeting") return { ...targetingApiFixture, ...body } as T;
  if (path === "/companies") return companiesApiFixture as T;
  if (path.startsWith("/companies/")) {
    const id = path.slice("/companies/".length);
    const row = companiesApiFixture.find((c) => c.id === id);
    return { ...row, ...body } as T;
  }
  if (path === "/approvals") return approvalsApiFixture as T;
  if (/^\/approvals\/[^/]+\/decision$/.test(path)) {
    return { ok: true, ...body } as T;
  }
  if (path.startsWith("/insights")) return insightsApiFixture as T;
  if (path === "/skills-gap") return skillsGapApiFixture as T;
  if (path === "/lenses") return lensesApiFixture as T;
  if (path === "/tweaks") return { ...tweaksApiFixture, ...body } as T;
  if (/^\/jobs\/[^/]+\/state$/.test(path)) {
    return {
      status: null,
      note: null,
      dismissReason: null,
      feedback: null,
      ...body,
    } as T;
  }
  if (path.startsWith("/jobs/")) {
    const id = decodeURIComponent(path.slice("/jobs/".length));
    const job = seedJobs.find((j) => j.id === id);
    if (!job) throw new Error(`mockBffFetch: no fixture job "${id}"`);
    return job as T;
  }
  if (path.startsWith("/jobs")) {
    const { lens, sort } = parseJobsQuery(path);
    return jobsResponseFixture(lens, sort) as T;
  }
  throw new Error(`mockBffFetch: no fixture for path "${path}"`);
}
