import { NextResponse } from "next/server";
import { getApprovals } from "@/lib/api/approvals";

export function GET(): NextResponse {
  return NextResponse.json(getApprovals());
}
