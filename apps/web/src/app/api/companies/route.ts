import { NextResponse } from "next/server";
import { getCompanies } from "@/lib/api/companies";

export function GET(): NextResponse {
  return NextResponse.json(getCompanies());
}
