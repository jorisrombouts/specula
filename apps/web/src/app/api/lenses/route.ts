import { NextResponse } from "next/server";
import { getLenses } from "@/lib/api/lenses";
import { bffFetch } from "@/lib/api/bff";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getLenses());
}

export async function POST(request: Request): Promise<NextResponse> {
  const body = await request.json();
  const created = await bffFetch("/lenses", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return NextResponse.json(created, { status: 201 });
}
