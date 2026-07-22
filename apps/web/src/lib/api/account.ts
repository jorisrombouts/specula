import type { ExportBundle } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// Server-side: the caller's full GDPR data export (proxied by the export route handler,
// which serves it as a downloadable attachment).
export async function getAccountExport(): Promise<ExportBundle> {
  return bffFetch<ExportBundle>("/account/export");
}

// Client-side: permanently delete the caller's account and all of their data (FK cascade).
// The caller is responsible for signing the user out afterwards.
export async function deleteAccount(): Promise<void> {
  const res = await fetch("/api/account", { method: "DELETE" });
  if (!res.ok) throw new Error(`Account deletion failed (${res.status})`);
}
