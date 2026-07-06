import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const body = await request.json();
  const updated = await bffFetch(`/companies/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return NextResponse.json(updated);
}
