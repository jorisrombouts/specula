import { NextResponse } from "next/server";
import { getInsights } from "@/lib/api/insights";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getInsights());
}
