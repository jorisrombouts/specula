import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const body = await request.json();
  try {
    const updated = await bffFetch(`/companies/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return NextResponse.json(updated);
  } catch {
    // bffFetch not wired yet (Frontend-wiring lane pending).
    return NextResponse.json({ error: "not wired" }, { status: 501 });
  }
}
