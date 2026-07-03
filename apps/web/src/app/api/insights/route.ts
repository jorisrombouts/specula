import { NextResponse } from "next/server";
import { getInsights } from "@/lib/api/insights";

export function GET(): NextResponse {
  return NextResponse.json(getInsights());
}
