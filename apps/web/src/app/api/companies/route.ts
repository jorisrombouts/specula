import { NextResponse } from "next/server";
import { getCompanies } from "@/lib/api/companies";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getCompanies());
}
