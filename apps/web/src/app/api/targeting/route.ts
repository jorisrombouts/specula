import { NextResponse } from "next/server";
import { targeting } from "@/lib/seed/data";

export function GET(): NextResponse {
  return NextResponse.json(targeting);
}
