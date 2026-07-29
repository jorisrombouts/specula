export type Mode = "Remote" | "Hybrid" | "On-site";
export type JobStatus = "Saved" | "Applied" | "Interviewing" | "Offer" | "Dismissed";
export type JobSort = "match" | "deadline" | "new";

export interface Factors { role: number; skill: number; loc: number }

export interface Job {
  id: string; company: string; logo: string; title: string;
  city: string; country: string; hq: string; mode: Mode; flag: string;
  match: number; factors: Factors; overlap: [number, number];
  seniority: string; edu: string; deadlineDays: number; salary: string | null;
  posted: string; status: JobStatus | null; isNew: boolean; stillOpen: boolean;
  originVerified: boolean; hqConf: number; redFlag?: string;
  stack: string[]; niceToHave: string[]; visa: string; langs: string[];
  contract: string; geo: string; confidence: number; dismissReason?: string;
  responsibilities: string[]; summary: string; rationale: string;
  sourceUrl: string;
}

export interface Lens {
  id: string; name: string; short: string; active: boolean;
  scope: string; modes: Mode[]; origin: string; focus: string; seeds: string[];
}
export interface LensSummary extends Lens { count: number; isNew: number; isDefault: boolean }

// ⚠ Enum source of truth. Mirrored in apps/api/specula_api/schemas/candidate.py
// (Mode / Visa / CefrLevel Literals). Keep both in sync.
export type CefrLevel = "Native" | "C2" | "C1" | "B2" | "B1" | "A2" | "A1";
export const CEFR_LEVELS: readonly CefrLevel[] = [
  "Native", "C2", "C1", "B2", "B1", "A2", "A1",
];

export const VISA_OPTIONS = [
  "EU/EEA/Swiss citizen — no sponsorship",
  "Have EU work/residence permit — no sponsorship",
  "Require visa sponsorship",
  "Require relocation + sponsorship",
] as const;
export type Visa = (typeof VISA_OPTIONS)[number];

export const WORK_MODES: readonly Mode[] = ["Remote", "Hybrid", "On-site"];

export interface LanguageEntry { language: string; level: CefrLevel }
export interface EducationEntry {
  degree: string; field: string; institution: string; year: number | null;
}
export interface ProjectEntry { name: string; note: string }
export interface ExperienceEntry {
  role: string; org: string; startYear: number | null; endYear: number | null;
}

export interface Candidate {
  name: string; initials: string; title: string; location: string;
  workMode: Mode[]; visa: Visa | ""; years: number;
  education: EducationEntry[]; languages: LanguageEntry[]; skills: string[];
  projects: ProjectEntry[]; experience: ExperienceEntry[];
}

export type Seniority =
  | "Junior"
  | "Mid"
  | "Senior"
  | "Staff"
  | "Principal"
  | "Lead"
  | "Manager"
  | "Director";
export const SENIORITY_LEVELS: readonly Seniority[] = [
  "Junior",
  "Mid",
  "Senior",
  "Staff",
  "Principal",
  "Lead",
  "Manager",
  "Director",
];

export interface Targeting {
  roleTitles: string[]; seniority: Seniority[]; mustHaves: string[];
  avoid: string[]; preferences: string;
}
export interface Company {
  name: string; logo: string; domain: string; ats: string; hq: string;
  flag: string; conf: number; open: number; comp: string; added: string;
  unverified?: boolean;
}
export interface Approval {
  id: string; name: string; logo: string; domain: string; ats: string;
  hq: string; flag: string; query: string; why: string;
  careersUrl: string | null; roles: number;
  unverified?: boolean;
}
export interface SkillDemand { skill: string; pct: number; delta: number; up: boolean; gap?: boolean }
export interface TrendSeries { name: string; color: string; data: number[] }
export interface Trend { weeks: string[]; series: TrendSeries[] }
export interface SeniorityMix { k: string; v: number }
export interface ModeMix { k: string; v: number; color: string }
export interface SalaryBand { band: string; lo: number; hi: number }
export interface ActiveCompany { name: string; n: number }
export interface Insights {
  period: string; totalAnalysed: number; lowConfExcluded: number;
  skillDemand: SkillDemand[]; trend: Trend;
  seniorityMix: SeniorityMix[]; modeMix: ModeMix[];
  salary: SalaryBand[]; activeCompanies: ActiveCompany[];
}
export interface SkillsGap { skill: string; roles: number; note: string }

export interface JobsResponse { jobs: Job[]; lenses: LensSummary[]; sort: JobSort }

export interface RunStats { found: number; new: number; closed: number; lowConfExcluded: number; errors: number; scored: number }
export interface Run {
  id: string; kind: "scheduled" | "on_demand" | "rescore" | "refresh";
  status: "queued" | "running" | "done" | "error";
  startedAt: string | null; finishedAt: string | null;
  stats: RunStats; createdAt: string; tokens?: RunTokens | null;
}

export interface LlmCost {
  id: string; runId: string | null; companyId: string | null;
  stage: string; model: string;
  promptTokens: number; completionTokens: number; embedTokens: number;
  createdAt: string;
}
export interface RunTokens { totalTokens: number; durationMs: number | null }
export interface TokenPoint { date: string; totalTokens: number; runs: number }
export interface TokensByStage { stage: string; totalTokens: number }
export interface DashboardSummary {
  totalTokens: number; runCount: number;
  tokensByStage: TokensByStage[]; tokensByDay: TokenPoint[]; recentRuns: Run[];
}
// A data-export blob is a heterogeneous dump; DATA owns the row shapes on both ends,
// so arrays are intentionally `unknown[]` here (a deliberate type, not a placeholder).
export interface ExportBundle {
  exportedAt: string;
  candidate: unknown; targeting: unknown;
  companies: unknown[]; postings: unknown[]; scores: unknown[];
  lenses: unknown[]; runs: unknown[]; llmCosts: LlmCost[];
}
export interface RateLimitError { error: "rate_limited"; retryAfterS: number }
