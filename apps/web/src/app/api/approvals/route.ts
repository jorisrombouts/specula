import { NextResponse } from "next/server";
import { approvals } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(approvals);
}
