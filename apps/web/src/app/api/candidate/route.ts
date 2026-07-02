import { NextResponse } from "next/server";
import { getCandidate } from "@/lib/api/candidate";

export function GET(): NextResponse {
  return NextResponse.json(getCandidate());
}
