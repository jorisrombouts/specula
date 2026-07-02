import { NextResponse } from "next/server";
import { getLenses } from "@/lib/api/lenses";

export function GET(): NextResponse {
  return NextResponse.json(getLenses());
}
