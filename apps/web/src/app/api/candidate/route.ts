import { NextResponse } from "next/server";
import { candidate } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(candidate);
}
