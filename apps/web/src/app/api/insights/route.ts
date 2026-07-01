import { NextResponse } from "next/server";
import { insights } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(insights);
}
