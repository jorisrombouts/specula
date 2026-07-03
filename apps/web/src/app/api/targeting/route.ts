import { NextResponse } from "next/server";
import { getTargeting } from "@/lib/api/targeting";

export function GET(): NextResponse {
  return NextResponse.json(getTargeting());
}
