import type { LensSummary, Mode } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

export async function getLenses(): Promise<LensSummary[]> {
  return bffFetch<LensSummary[]>("/lenses");
}

// The editable lens payload (camelCase; `origin` carries the origin_rule value).
export type LensPatch = {
  name: string;
  short: string;
  scope: string;
  modes: Mode[];
  origin: string;
  focus: string;
  seeds: string[];
  active: boolean;
};

export async function createLens(patch: LensPatch): Promise<LensSummary> {
  const res = await fetch("/api/lenses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Failed to create lens (${res.status})`);
  return (await res.json()) as LensSummary;
}

export async function updateLens(
  id: string,
  patch: Partial<LensPatch>,
): Promise<LensSummary> {
  const res = await fetch(`/api/lenses/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Failed to update lens (${res.status})`);
  return (await res.json()) as LensSummary;
}

export async function deleteLens(id: string): Promise<void> {
  const res = await fetch(`/api/lenses/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete lens (${res.status})`);
}
