import type { Seniority, Targeting } from "@specula/shared-types";
import { SENIORITY_LEVELS } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// FastAPI's `TargetingOut` (camelCased). `seniority` is lenient server-side
// (`list[str]`) and is sanitized to the canonical ladder below.
type TargetingApiOut = {
  roleTitles: string[];
  seniority: string[];
  mustHaves: string[];
  avoid: string[];
  preferences: string | null;
};

export async function getTargeting(): Promise<Targeting> {
  const api = await bffFetch<TargetingApiOut>("/targeting");
  return {
    roleTitles: api.roleTitles,
    // drop legacy / out-of-ladder seniority values so the multi-select gets valid input
    seniority: api.seniority.filter((s): s is Seniority =>
      (SENIORITY_LEVELS as readonly string[]).includes(s),
    ),
    mustHaves: api.mustHaves,
    avoid: api.avoid,
    preferences: api.preferences ?? "",
  };
}

// The whole targeting form is editable; the patch is the full contract.
export type TargetingPatch = Targeting;

// Client-side: persist through the BFF route (which proxies to FastAPI
// `PUT /targeting`, a full replace).
export async function saveTargeting(patch: TargetingPatch): Promise<void> {
  const res = await fetch("/api/targeting", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      roleTitles: patch.roleTitles,
      seniority: patch.seniority,
      mustHaves: patch.mustHaves,
      avoid: patch.avoid,
      preferences: patch.preferences,
    }),
  });
  if (!res.ok) throw new Error(`Failed to save targeting (${res.status})`);
}
