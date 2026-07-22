import { NextResponse } from "next/server";
import type { ExportBundle } from "@specula/shared-types";
import { getAccountExport } from "@/lib/api/account";

// Serves the caller's data export as a downloadable JSON file. The browser never calls
// FastAPI directly — this route mints the service JWT (via bffFetch) and proxies.
export async function GET(): Promise<NextResponse<ExportBundle>> {
  const bundle = await getAccountExport();
  return NextResponse.json(bundle, {
    headers: {
      "Content-Disposition": 'attachment; filename="specula-export.json"',
    },
  });
}
