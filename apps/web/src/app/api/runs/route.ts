import { NextResponse } from "next/server";
import type { Run } from "@specula/shared-types";
import { bffFetch } from "@/lib/api/bff";

// Triggers a new pipeline run (mirrors the approvals decision route's
// client-through-BFF pattern). The browser never calls FastAPI directly.
export async function POST(): Promise<NextResponse<Run>> {
  const run = await bffFetch<Run>("/runs", { method: "POST" });
  return NextResponse.json(run, { status: 201 });
}
