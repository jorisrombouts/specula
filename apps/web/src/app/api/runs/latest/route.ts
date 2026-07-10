import { NextResponse } from "next/server";
import type { Run } from "@specula/shared-types";
import { getLatestRun } from "@/lib/api/runs";

// Also polled directly from the client (useLatestRun), not just used for the
// server-rendered initial sidebar state.
export async function GET(): Promise<NextResponse<Run | null>> {
  return NextResponse.json(await getLatestRun());
}
