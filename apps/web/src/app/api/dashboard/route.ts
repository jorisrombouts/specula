import { NextResponse } from "next/server";
import { getDashboard } from "@/lib/api/dashboard";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getDashboard());
}
