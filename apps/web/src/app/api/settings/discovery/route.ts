import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

// Read/update the user's discovery search cap. Proxies to FastAPI /settings/discovery; the
// browser never calls FastAPI directly.
export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await bffFetch("/settings/discovery"));
}

export async function PUT(request: Request): Promise<NextResponse> {
  const body = await request.json();
  const updated = await bffFetch("/settings/discovery", {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return NextResponse.json(updated);
}
