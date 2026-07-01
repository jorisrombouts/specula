import { NextResponse } from "next/server";
import { jobs, lenses } from "@/lib/seed/data";
import { deriveLensSummaries } from "@/lib/seed/logic";

export function GET(): NextResponse {
  return NextResponse.json(deriveLensSummaries(lenses, jobs));
}
