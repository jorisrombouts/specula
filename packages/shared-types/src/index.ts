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
}

export interface Lens {
  id: string; name: string; short: string; active: boolean;
  scope: string; modes: Mode[]; origin: string; focus: string; seeds: string[];
}
export interface LensSummary extends Lens { count: number; isNew: number }

export interface Candidate {
  name: string; initials: string; title: string; location: string;
  workMode: string; visa: string; years: number; education: string;
  languages: string[]; skills: string[];
  projects: { name: string; note: string }[];
  experience: { role: string; org: string; period: string }[];
}
export interface Targeting {
  roleTitles: string[]; seniority: string[]; mustHaves: string[];
  avoid: string[]; preferences: string;
}
export interface Company {
  name: string; logo: string; domain: string; ats: string; hq: string;
  flag: string; conf: number; open: number; comp: string; added: string;
  unverified?: boolean;
}
export interface Approval {
  id: string; name: string; logo: string; domain: string; ats: string;
  hq: string; flag: string; query: string; why: string; roles: number;
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
