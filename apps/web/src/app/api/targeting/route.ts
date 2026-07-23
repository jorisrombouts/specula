import { NextResponse } from "next/server";
import { getTargeting } from "@/lib/api/targeting";
import { bffFetch } from "@/lib/api/bff";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await getTargeting());
}

export async function PUT(request: Request): Promise<NextResponse> {
  const body = await request.json();
  const updated = await bffFetch("/targeting", {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return NextResponse.json(updated);
}
