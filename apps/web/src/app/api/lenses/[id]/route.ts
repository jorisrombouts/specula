import { NextResponse } from "next/server";
import { bffFetch } from "@/lib/api/bff";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const body = await request.json();
  const updated = await bffFetch(`/lenses/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return NextResponse.json(updated);
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  await bffFetch(`/lenses/${id}`, { method: "DELETE" });
  return new NextResponse(null, { status: 204 });
}
