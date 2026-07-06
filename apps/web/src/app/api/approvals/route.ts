import { NextResponse } from "next/server";
import { getApprovals } from "@/lib/api/approvals";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getApprovals());
}
