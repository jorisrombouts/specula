import { bffFetch } from "@/lib/api/bff";

// Server-side: the user's discovery search cap (their override or the global default).
export async function getDiscoverySettings(): Promise<{ maxSearches: number }> {
  return bffFetch<{ maxSearches: number }>("/settings/discovery");
}

// Client-side: persist the search cap through the BFF route. Throws on a non-2xx.
export async function saveDiscoverySettings(
  maxSearches: number,
): Promise<void> {
  const res = await fetch("/api/settings/discovery", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ maxSearches }),
  });
  if (!res.ok)
    throw new Error(`Failed to save discovery settings (${res.status})`);
}
