import { NextResponse } from "next/server";
import { companies } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(companies);
}
