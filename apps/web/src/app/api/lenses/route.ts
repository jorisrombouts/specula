import { NextResponse } from "next/server";
import { getLenses } from "@/lib/api/lenses";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getLenses());
}
