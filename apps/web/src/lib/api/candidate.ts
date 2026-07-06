import type { Candidate } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// Shape of FastAPI's `CandidateOut` (apps/api/specula_api/schemas/candidate.py),
// camelCased by its `to_camel` alias generator. `candidate_profiles` has no
// name/initials/title columns — `headline` is the profile's freeform title.
type CandidateApiOut = {
  headline: string | null;
  location: string | null;
  workMode: string | null;
  visa: string | null;
  years: number | null;
  education: string | null;
  languages: string[];
  skills: string[];
  projects: { name: string; note: string }[];
  experience: { role: string; org: string; period: string }[];
};

// Server-side: maps the API's profile fields onto the TS `Candidate` contract.
// `name`/`initials` aren't stored server-side at all (the sidebar sources the
// display name from the session instead); they default to "".
export async function getCandidate(): Promise<Candidate> {
  const api = await bffFetch<CandidateApiOut>("/candidate");
  return {
    name: "",
    initials: "",
    title: api.headline ?? "",
    location: api.location ?? "",
    workMode: api.workMode ?? "",
    visa: api.visa ?? "",
    years: api.years ?? 0,
    education: api.education ?? "",
    languages: api.languages,
    skills: api.skills,
    projects: api.projects,
    experience: api.experience,
  };
}

// The editable subset of the candidate form, saved via `PUT /api/candidate`.
export type CandidatePatch = Omit<Candidate, "name" | "initials">;

// Client-side: persist the candidate form through the BFF route (which proxies
// to FastAPI `PUT /candidate`, a full replace of the profile).
export async function saveCandidate(patch: CandidatePatch): Promise<void> {
  const res = await fetch("/api/candidate", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      headline: patch.title,
      location: patch.location,
      workMode: patch.workMode,
      visa: patch.visa,
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
