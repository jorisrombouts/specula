import type {
  Candidate,
  EducationEntry,
  ExperienceEntry,
  LanguageEntry,
  Mode,
  ProjectEntry,
  Visa,
} from "@specula/shared-types";
import { VISA_OPTIONS, WORK_MODES } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// Shape of FastAPI's `CandidateOut` (camelCased). The read model is lenient — it can
// surface legacy / pre-enum values (e.g. a `visa` free-text string or an out-of-set
// work mode) rather than 500ing — so `workMode`/`visa` are plain strings here and are
// sanitized below.
type CandidateApiOut = {
  headline: string | null;
  location: string | null;
  workMode: string[];
  visa: string | null;
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
    // Sanitize legacy/out-of-enum reads to the strict client types: drop unknown work
    // modes, and show an unknown visa as unset ("") so the controlled inputs get valid
    // values and the user simply re-picks.
    workMode: api.workMode.filter((m): m is Mode =>
      (WORK_MODES as readonly string[]).includes(m),
    ),
    visa: (VISA_OPTIONS as readonly string[]).includes(api.visa ?? "")
      ? (api.visa as Visa)
      : "",
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
