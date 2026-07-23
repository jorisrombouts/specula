import type {
  Candidate,
  EducationEntry,
  ExperienceEntry,
  LanguageEntry,
  Mode,
  ProjectEntry,
  Visa,
} from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// Shape of FastAPI's `CandidateOut` (camelCased). `candidate_profiles` has no
// name/initials/title columns — `headline` is the profile's freeform title.
type CandidateApiOut = {
  headline: string | null;
  location: string | null;
  workMode: Mode[];
  visa: Visa | null;
  years: number | null;
  education: EducationEntry[];
  languages: LanguageEntry[];
  skills: string[];
  projects: ProjectEntry[];
  experience: ExperienceEntry[];
};

// Server-side: maps the API's profile fields onto the TS `Candidate` contract.
// `name`/`initials` aren't stored server-side (the sidebar sources the display
// name from the session); they default to "".
export async function getCandidate(): Promise<Candidate> {
  const api = await bffFetch<CandidateApiOut>("/candidate");
  return {
    name: "",
    initials: "",
    title: api.headline ?? "",
    location: api.location ?? "",
    workMode: api.workMode,
    visa: api.visa ?? "",
    years: api.years ?? 0,
    education: api.education,
    languages: api.languages,
    skills: api.skills,
    projects: api.projects,
    experience: api.experience,
  };
}

// The editable subset of the candidate form, saved via `PUT /api/candidate`.
export type CandidatePatch = Omit<Candidate, "name" | "initials">;

// Client-side: persist the candidate form through the BFF route (which proxies
// to FastAPI `PUT /candidate`, a full replace). `visa: ""` (unset) maps to null.
export async function saveCandidate(patch: CandidatePatch): Promise<void> {
  const res = await fetch("/api/candidate", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      headline: patch.title,
      location: patch.location,
      workMode: patch.workMode,
      visa: patch.visa === "" ? null : patch.visa,
      years: patch.years,
      education: patch.education,
      languages: patch.languages,
      skills: patch.skills,
      projects: patch.projects,
      experience: patch.experience,
    }),
  });
  if (!res.ok) throw new Error(`Failed to save candidate (${res.status})`);
}
