import { NextResponse } from "next/server";
import { getTargeting } from "@/lib/api/targeting";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getTargeting());
}
