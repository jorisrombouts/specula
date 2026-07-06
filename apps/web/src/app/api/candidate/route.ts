import { NextResponse } from "next/server";
import { getCandidate } from "@/lib/api/candidate";
import { bffFetch } from "@/lib/api/bff";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getCandidate());
}

export async function PUT(request: Request): Promise<NextResponse> {
  const body = await request.json();
  const updated = await bffFetch("/candidate", {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return NextResponse.json(updated);
}
